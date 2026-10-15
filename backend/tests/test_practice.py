"""PRD v2 Step 3: Replay My Mistakes. The engine is scripted (`FakeAnalyser`): any move scores 0, so a move is unsound only
by the refutation rule, which these tests set up on real boards (M1: the rook on h7 hangs to the queen; M2: the queen on d5
can be taken by the rook on d2)."""

import json
import random
import sqlite3
from datetime import timedelta

import chess
import pytest

from app.db.schema import connect
from app.detectors import prd_rules as R
from app.engine.evidence import EvidenceAnalysis, Line
from app.learner import assessment as A
from app.learner import practice as P
from tests.test_assessment import CFG, FORBIDDEN_KEYS, T0, Store, finish, keys


class FakeAnalyser:
    """Scripted engine: a position's lines are its three best legal moves by the material they leave on the board (White's
    point of view, 100 cp a point). A capture that wins the queen scores +900, so ignoring it loses far more than 100 cp."""

    config = CFG

    def analyse(self, board, depth=None):
        scored = []
        for m in board.legal_moves:
            b = board.copy(stack=False)
            b.push(m)
            scored.append((100 * (R.material(b, chess.WHITE) - R.material(b, chess.BLACK)), m.uci()))
        scored.sort(reverse=board.turn == chess.WHITE)
        sign = 1 if board.turn == chess.WHITE else -1
        scored.sort(key=lambda t: sign * t[0], reverse=True)
        lines = tuple(Line(u, (u,), cp, None, None, 18) for cp, u in scored[:3])
        return EvidenceAnalysis(board.fen(), CFG.id, lines)

# Practice boards. M1: White's rook on a1 is attacked by the bishop on c3 (Bxa1); M2: the queen on d5 is free for the rook on d2.
M1_PRACTICE_FEN = "4k3/8/8/8/8/2b5/8/R5K1 w - - 0 {n}"
M1_PRACTICE = {
    "target_squares": ["a1"], "best_move": {"uci": "a1a2", "san": "Ra2"},
    "refutation_line": {"uci": ["c3a1"], "san": ["Bxa1"]}, "material_swing": 5,
}
# answers on the scripted boards
RIGHT = {"M1": ("a1", "a1a2"), "M2": ("d5", "d2d5")}
WRONG_MOVE = "g1f1"  # leaves the rook (M1) and the queen (M2) alone: not sound
LATER = 7  # seconds after the previous step

PRACTICE_KEYS = FORBIDDEN_KEYS | {"allowed", "board_line", "good_moves", "original", "verdict", "avoids", "sound"}


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "store.sqlite3")
    yield c
    c.close()


@pytest.fixture
def store(conn):
    s = Store(conn)
    s.fill(m1=20, m2=20, clean=14)  # held-out: enough for both starting tests
    for _ in range(8):
        s.position("M1", pool="PRACTICE", fen=M1_PRACTICE_FEN.format(n=s.n + 2), override=M1_PRACTICE)
    for _ in range(6):
        s.position("M2", pool="PRACTICE")
    for t in A.TYPES:  # the starting tests are done: practice is unlocked
        finish(conn, A.start_baseline(conn, t, rng=random.Random(3), now=T0)["assessment_id"])
    return s


def at(seconds):
    return T0 + timedelta(minutes=10, seconds=seconds)


def begin(conn, t="M1", seconds=0):
    sid = P.start_session(conn, t, now=at(seconds))["session_id"]
    return sid, P.get_session(conn, sid, now=at(seconds))


def play(conn, sid, view, *, good=True, tap=None, hints=0, clock=0):
    """One attempt on the current position: the question, the move; returns the feedback view."""
    cur = view["current"]
    t = view["mistake_type"]
    right_tap, right_move = RIGHT[t]
    for _ in range(hints):
        view = P.hint(conn, sid, cur["ord"], now=at(clock))
    wrong_tap = next(sq for sq in cur["tap_squares"] if sq != right_tap)
    view = P.submit_recognition(conn, sid, cur["ord"], tap or (right_tap if good else wrong_tap), now=at(clock + 2))
    return P.submit_move(conn, sid, cur["ord"], right_move if good else WRONG_MOVE, FakeAnalyser(), now=at(clock + LATER))


def finish_session(conn, sid, view, **kw):
    clock = 0
    while view["current"]:
        fb = play(conn, sid, view, clock=clock, **kw)
        view = P.next_position(conn, sid, fb["current"]["ord"], now=at(clock + 10))
        clock += 20
    return view


# --- starting ------------------------------------------------------------------------------------------------------------


def test_practice_is_locked_until_the_baseline_for_the_type_is_done(conn):
    s = Store(conn)
    s.fill(m1=20, m2=20, clean=14)
    for _ in range(6):
        s.position("M1", pool="PRACTICE", fen=M1_PRACTICE_FEN.format(n=s.n + 2), override=M1_PRACTICE)
    with pytest.raises(A.AssessmentError) as e:
        P.start_session(conn, "M1")
    assert e.value.code == "baseline_needed"
    finish(conn, A.start_baseline(conn, "M1", rng=random.Random(1), now=T0)["assessment_id"])
    assert P.home_status(conn, "M1")["unlocked"] and not P.home_status(conn, "M2")["unlocked"]
    assert P.start_session(conn, "M1", now=at(0))["resumed"] is False
    with pytest.raises(A.AssessmentError):  # the other type is still locked
        P.start_session(conn, "M2")


def test_a_set_aside_baseline_does_not_unlock_practice(store):
    conn = store.conn
    first = conn.execute("SELECT id FROM assessment WHERE mistake_type = 'M1'").fetchone()[0]
    A.supersede_baseline(conn, first, "retake")
    with pytest.raises(A.AssessmentError) as e:
        P.start_session(conn, "M1")
    assert e.value.code == "baseline_needed"


def test_a_session_has_five_practice_positions_from_different_games_newest_first(store):
    conn = store.conn
    sid, view = begin(conn)
    rows = conn.execute(
        "SELECT p.pool, p.game_id, g.played_at, sp.ord FROM practice_session_position sp JOIN position p ON p.id = sp.position_id"
        " JOIN game g ON g.id = p.game_id WHERE sp.session_id = ? ORDER BY sp.ord", (sid,)).fetchall()
    assert len(rows) == 5 and {r["pool"] for r in rows} == {"PRACTICE"}
    assert len({r["game_id"] for r in rows}) == 5
    assert [r["played_at"] for r in rows] == sorted((r["played_at"] for r in rows), reverse=True)
    assert view["total"] == 5 and view["done"] == 0 and view["repeat_games"] is False


def test_starting_freezes_the_real_game_window_once_and_a_second_start_resumes(store):
    conn = store.conn
    assert conn.execute("SELECT COUNT(*) FROM baseline_window WHERE mistake_type = 'M1'").fetchone()[0] == 0
    sid, _ = begin(conn)
    frozen = conn.execute("SELECT game_ids_json, frozen_at FROM baseline_window WHERE mistake_type = 'M1'").fetchall()
    assert len(frozen) >= 1
    assert P.start_session(conn, "M1", now=at(500)) == {"session_id": sid, "resumed": True}
    assert [tuple(r) for r in conn.execute("SELECT game_ids_json, frozen_at FROM baseline_window WHERE mistake_type = 'M1'")] \
        == [tuple(r) for r in frozen]
    assert conn.execute("SELECT COUNT(*) FROM baseline_window WHERE mistake_type = 'M2'").fetchone()[0] == 0


def test_selection_skips_seen_boards_wrong_kind_and_held_out_and_flags_repeat_games(conn):
    s = Store(conn)
    s.fill(m1=20, m2=20, clean=14)
    for t in A.TYPES:
        finish(conn, A.start_baseline(conn, t, rng=random.Random(3), now=T0)["assessment_id"])
    shared = s.game("PRACTICE")
    ok = [s.position("M1", pool="PRACTICE", game_id=shared, ply=ply) for ply in (10, 12, 14)]  # one game, three positions
    s.position("M1", pool="PRACTICE", lost_piece="moved")  # nothing to tap before the move (decision 14)
    seen = s.position("M1", pool="PRACTICE")
    conn.execute("UPDATE position SET excluded_reason = 'shown_in_explorer' WHERE id = ?", (seen,))
    retired = s.position("M1", pool="PRACTICE")
    conn.execute("UPDATE position SET retired_at = 'x' WHERE id = ?", (retired,))
    chosen = {r[0] for r in conn.execute("SELECT 1")}  # (placeholder to keep the shape simple)
    sid, view = begin(conn)
    ids = {r[0] for r in conn.execute("SELECT position_id FROM practice_session_position WHERE session_id = ?", (sid,))}
    assert ids == set(ok) and view["total"] == 3 and view["repeat_games"] is True  # same game three times: recorded
    assert not ids & {seen, retired} and chosen is not None


def test_too_few_practice_positions_blocks_with_a_message(conn):
    s = Store(conn)
    s.fill(m1=20, m2=20, clean=14)
    s.position("M1", pool="PRACTICE")
    s.position("M1", pool="PRACTICE")
    finish(conn, A.start_baseline(conn, "M1", rng=random.Random(3), now=T0)["assessment_id"])
    with pytest.raises(A.AssessmentError) as e:
        P.start_session(conn, "M1")
    assert e.value.code == "not_enough_practice_positions" and "2 of 3" in str(e.value)


# --- one full session ------------------------------------------------------------------------------------------------------


def test_a_full_session_works_end_to_end_with_retry_hints_and_summary(store):
    conn = store.conn
    sid, view = begin(conn)
    fens = [r[0] for r in conn.execute(
        "SELECT p.fen FROM practice_session_position sp JOIN position p ON p.id = sp.position_id WHERE session_id = ? ORDER BY ord",
        (sid,))]
    results = []
    clock = 0
    for i in range(5):
        cur = view["current"]
        assert cur["fen"] == fens[i] and cur["stage"] == "recognition" and cur["attempt"] == 1
        if i == 0:  # clean: right tap, sound move, no hint
            fb = play(conn, sid, view, clock=clock)
        elif i == 1:  # assisted: a hint, then right
            fb = play(conn, sid, view, hints=2, clock=clock)
        elif i == 2:  # not sound at first, then a retry that works
            fb = play(conn, sid, view, good=False, clock=clock)
            assert fb["current"]["feedback"]["sound"] is False
            view = P.retry(conn, sid, cur["ord"], now=at(clock + 9))
            assert view["current"]["attempt"] == 2 and view["current"]["stage"] == "recognition"
            assert view["current"]["hint_level"] == 0 and view["current"]["feedback"] is None
            fb = play(conn, sid, view, clock=clock + 10)
        else:
            fb = play(conn, sid, view, clock=clock)
        results.append(fb["current"]["feedback"])
        view = P.next_position(conn, sid, cur["ord"], now=at(clock + 30))
        clock += 40
    assert view["status"] == "completed" and view["current"] is None
    r = P.summary(conn, sid)
    assert r["assisted"] is True and r["completed"] == 5
    assert r["first_attempt_correct"] == 3  # positions 1, 4, 5 (position 2 used hints, position 3 needed a retry)
    assert r["assisted_correct"] == 1 and r["needed_retry"] == 1 and r["recognized"] == 3
    items = r["items"]
    assert [i["attempts"] for i in items] == [1, 1, 2, 1, 1]
    assert [i["hint_level"] for i in items] == [0, 2, 0, 0, 0]
    assert items[2]["first_attempt_correct"] is False and items[2]["needed_retry"] is True  # a retry is never a first attempt
    attempts = conn.execute("SELECT position_id, attempt_number, hint_level, move_sound FROM practice_attempt ORDER BY id").fetchall()
    assert len(attempts) == 6
    assert conn.execute("SELECT COUNT(*) FROM position WHERE exposure_status = 'PRACTICED'").fetchone()[0] == 5
    assert conn.execute("SELECT status FROM practice_session WHERE id = ?", (sid,)).fetchone()[0] == "completed"
    assert results[0]["verdict"] == "SOUND" and results[0]["tap_correct"] is True
    assert P.home_status(conn, "M1")["last_completed"] == sid and P.home_status(conn, "M1")["session"] is None
    # a new session can start once this one is complete
    assert P.start_session(conn, "M1", now=at(5000))["resumed"] is False


def test_feedback_shows_the_original_mistake_the_verdict_and_what_it_allowed(store):
    conn = store.conn
    sid, view = begin(conn)
    bad = play(conn, sid, view, good=False)["current"]["feedback"]
    assert bad["verdict"] == "NOT SOUND" and bad["avoids"] == "They could still win the piece."
    assert bad["game_move"] == {"uci": "g1g2", "san": "Kg2"} and "Bxa1" in bad["allowed"]
    assert bad["board_line"] == ["g1g2", "c3a1"]  # your move in the game, then what it allowed
    assert bad["target_squares"] == ["a1"] and bad["tap_correct"] is False and bad["your_move"]["uci"] == WRONG_MOVE
    sid2, view2 = begin(conn, "M2")
    ok = play(conn, sid2, view2)["current"]["feedback"]
    assert ok["verdict"] == "SOUND" and ok["tap_correct"] is True and ok["board_line"] == ["d2d5"]
    assert "Rxd5" in ok["allowed"]


def test_the_move_is_judged_with_the_sound_rules_not_only_the_engines_choice(store):
    conn = store.conn
    sid, view = begin(conn)
    cur = view["current"]
    P.submit_recognition(conn, sid, cur["ord"], "a1", now=at(1))
    # any move that stops the refutation is sound, not just the engine's first choice
    fb = P.submit_move(conn, sid, cur["ord"], "a1b1", FakeAnalyser(), now=at(5))
    assert fb["current"]["feedback"]["sound"] is True


# --- no leaks ---------------------------------------------------------------------------------------------------------------


def test_nothing_about_the_answer_is_shown_before_the_first_attempt_and_only_the_current_board(store):
    conn = store.conn
    sid, view = begin(conn)
    fens = [r[0] for r in conn.execute(
        "SELECT p.fen FROM practice_session_position sp JOIN position p ON p.id = sp.position_id WHERE session_id = ? ORDER BY ord",
        (sid,))]
    cur = view["current"]
    for body in (view, P.get_session(conn, sid, now=at(1))):  # fetching twice changes nothing
        assert not PRACTICE_KEYS & set(keys(body)), PRACTICE_KEYS & set(keys(body))
        assert [f for f in fens if f in json.dumps(body)] == [cur["fen"]]  # no later board
        assert body["current"]["hints"] == [] and body["current"]["feedback"] is None
    # after the question is answered the answer is still not shown
    body = P.submit_recognition(conn, sid, cur["ord"], "a1", now=at(3))
    assert body["current"]["stage"] == "move" and not PRACTICE_KEYS & set(keys(body))
    assert "target_squares" not in json.dumps(body) and "Bxa1" not in json.dumps(body)
    # the move reveals the feedback
    body = P.submit_move(conn, sid, cur["ord"], "a1a2", FakeAnalyser(), now=at(9))
    assert body["current"]["feedback"]["target_squares"] == ["a1"]


def test_a_hint_shows_only_its_own_rung(store):
    conn = store.conn
    s = store
    sid, view = begin(conn)
    cur = view["current"]
    h1 = P.hint(conn, sid, cur["ord"], now=at(1))["current"]
    assert [h["level"] for h in h1["hints"]] == [1] and "target_squares" not in json.dumps(h1)
    assert "Bxa1" not in json.dumps(h1) and '"a1"' not in json.dumps(h1["hints"])
    h2 = P.hint(conn, sid, cur["ord"], now=at(2))["current"]
    assert [h["level"] for h in h2["hints"]] == [1, 2] and h2["hints"][1]["squares"] == ["a1"]
    assert "Bxa1" not in json.dumps(h2)
    h3 = P.hint(conn, sid, cur["ord"], now=at(3))["current"]
    assert [h["level"] for h in h3["hints"]] == [1, 2, 3] and "Bxa1" in h3["hints"][2]["text"]
    again = P.hint(conn, sid, cur["ord"], now=at(4))["current"]  # capped at the third rung
    assert again["hint_level"] == 3 and len(again["hints"]) == 3
    assert s is store


def test_held_out_positions_never_appear_in_practice(store):
    conn = store.conn
    heldout = [r[0] for r in conn.execute("SELECT fen FROM position WHERE pool = 'HELDOUT'")]
    sid, view = begin(conn)
    bodies = [view]
    while view["current"]:
        fb = play(conn, sid, view)
        bodies.append(fb)
        view = P.next_position(conn, sid, fb["current"]["ord"], now=at(500))
        bodies.append(view)
    bodies.append(P.summary(conn, sid))
    text = json.dumps(bodies)
    assert not [f for f in heldout if f'"{f}"' in text]  # quoted: one board's text can be the start of another's
    with pytest.raises(sqlite3.IntegrityError, match="practice uses only"):
        conn.execute("INSERT INTO practice_session_position (session_id, position_id, ord) VALUES (?, ?, 9)",
                     (sid, conn.execute("SELECT id FROM position WHERE pool = 'HELDOUT' LIMIT 1").fetchone()[0]))


# --- resume ----------------------------------------------------------------------------------------------------------------


def test_an_interrupted_session_resumes_at_the_same_position_step_and_hint_state(store, tmp_path):
    conn = store.conn
    sid, view = begin(conn)
    cur = view["current"]
    P.hint(conn, sid, cur["ord"], now=at(1))
    P.hint(conn, sid, cur["ord"], now=at(2))
    P.submit_recognition(conn, sid, cur["ord"], "a1", now=at(3))
    reopened = connect(tmp_path / "store.sqlite3")  # the app was closed and opened again
    assert P.start_session(reopened, "M1", now=at(900)) == {"session_id": sid, "resumed": True}
    back = P.get_session(reopened, sid, now=at(901))["current"]
    assert (back["fen"], back["stage"], back["hint_level"], back["your_tap"]) == (cur["fen"], "move", 2, "a1")
    assert [h["level"] for h in back["hints"]] == [1, 2]
    P.submit_move(reopened, sid, cur["ord"], "a1a2", FakeAnalyser(), now=at(910))
    again = P.get_session(reopened, sid, now=at(920))["current"]  # resumed on the feedback step
    assert again["stage"] == "feedback" and again["feedback"]["sound"] is True
    assert P.home_status(reopened, "M1")["session"] == {"session_id": sid, "done": 0, "total": 5}


# --- the rules of the steps ------------------------------------------------------------------------------------------------


def test_steps_must_be_taken_in_order_on_the_current_position(store):
    conn = store.conn
    sid, view = begin(conn)
    cur = view["current"]
    with pytest.raises(A.AssessmentError) as e:  # a move before the question
        P.submit_move(conn, sid, cur["ord"], "h7h1", FakeAnalyser(), now=at(1))
    assert e.value.code == "wrong_step"
    with pytest.raises(A.AssessmentError) as e:  # the wrong position
        P.submit_recognition(conn, sid, cur["ord"] + 1, "h7", now=at(1))
    assert e.value.code == "not_current_position"
    other_side = next(sq for sq in ("c3", "e8") if sq not in cur["tap_squares"])
    with pytest.raises(A.AssessmentError) as e:  # M1 asks about your own pieces
        P.submit_recognition(conn, sid, cur["ord"], other_side, now=at(1))
    assert e.value.code == "tap_a_piece" and "your" in str(e.value)
    for step in (lambda: P.retry(conn, sid, cur["ord"], now=at(2)), lambda: P.next_position(conn, sid, cur["ord"], now=at(2))):
        with pytest.raises(A.AssessmentError) as e:  # not before the feedback
            step()
        assert e.value.code == "wrong_step"
    P.submit_recognition(conn, sid, cur["ord"], "none", now=at(3))  # "No immediate threat" is allowed, and never right here
    with pytest.raises(A.AssessmentError) as e:
        P.submit_recognition(conn, sid, cur["ord"], "a1", now=at(4))  # already answered
    assert e.value.code == "wrong_step"
    with pytest.raises(A.AssessmentError) as e:
        P.submit_move(conn, sid, cur["ord"], "a1a9", FakeAnalyser(), now=at(5))
    assert e.value.code == "illegal_move"
    fb = P.submit_move(conn, sid, cur["ord"], "a1a2", FakeAnalyser(), now=at(6))["current"]["feedback"]
    assert fb["tap_correct"] is False and fb["your_tap"] == "none"
    with pytest.raises(A.AssessmentError) as e:  # hints are for before the answer
        P.hint(conn, sid, cur["ord"], now=at(7))
    assert e.value.code == "wrong_step"


def test_the_summary_waits_for_the_last_position(store):
    sid, view = begin(store.conn)
    with pytest.raises(A.AssessmentError) as e:
        P.summary(store.conn, sid)
    assert e.value.code == "not_finished"
    finish_session(store.conn, sid, view)
    assert P.summary(store.conn, sid)["completed"] == 5
    with pytest.raises(A.AssessmentError) as e:
        P.hint(store.conn, sid, 0, now=at(9999))
    assert e.value.code == "session_completed"


def test_positions_not_got_right_on_their_own_come_back_in_a_later_session_and_clean_ones_do_not(store):
    conn = store.conn
    sid, view = begin(conn, "M2")  # 6 practice M2 positions: the first session takes 5
    clock = 0
    done = []
    for good in (True, False, True, False, True):
        fb = play(conn, sid, view, good=good, clock=clock)
        done.append(fb["current"]["ord"])
        view = P.next_position(conn, sid, fb["current"]["ord"], now=at(clock + 20))
        clock += 30
    assert view["status"] == "completed"
    sid2, view2 = begin(conn, "M2", seconds=2000)
    ids = [r[0] for r in conn.execute(
        "SELECT position_id FROM practice_session_position WHERE session_id = ? ORDER BY ord", (sid2,))]
    first = {r["position_id"]: r for r in conn.execute(
        "SELECT position_id, move_sound, hint_level FROM practice_attempt WHERE attempt_number = 1 AND move IS NOT NULL")}
    wrong_first = [p for p, r in first.items() if not (r["move_sound"] == 1 and r["hint_level"] == 0)]
    clean_first = [p for p, r in first.items() if r["move_sound"] == 1 and r["hint_level"] == 0]
    assert len(wrong_first) == 2 and len(clean_first) == 3
    assert set(wrong_first) <= set(ids) and not set(clean_first) & set(ids)  # the unseen one, then the two to repeat
    assert view2["total"] == 3 and P.available(conn, "M2")["unseen"] == 0


# --- the database rules ---------------------------------------------------------------------------------------------------


def test_one_open_session_per_type_and_attempts_belong_to_their_session(store):
    conn = store.conn
    sid, _ = begin(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO practice_session (user, mistake_type, status, started_at) VALUES (?, 'M1', 'created', 'x')",
                     (A.user(),))
    outsider = conn.execute(
        "SELECT id FROM position WHERE pool = 'PRACTICE' AND mistake_type = 'M1' AND id NOT IN"
        " (SELECT position_id FROM practice_session_position) LIMIT 1").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="position of its session"):
        conn.execute("INSERT INTO practice_attempt (session_id, position_id, attempt_number, hint_level, created_at)"
                     " VALUES (?, ?, 1, 0, 'x')", (sid, outsider))
    with pytest.raises(sqlite3.IntegrityError, match="never changed"):
        conn.execute("UPDATE practice_session_position SET position_id = ? WHERE session_id = ?", (outsider, sid))


# --- the first hint needs the game's moves -------------------------------------------------------------------------------


def test_hint_one_names_the_opponents_last_move_from_the_game(conn):
    s = Store(conn)
    gid = s.game("PRACTICE", pgn='[Event "x"]\n\n1. e4 e5 2. Nf3 Nc6 *')
    fen_after_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    pid = s.position("M1", pool="PRACTICE", game_id=gid, ply=1, fen=fen_after_e4)
    pos = conn.execute(
        "SELECT sp.ord, sp.position_id, sp.done_at, p.fen, p.ply, p.mistake_type, p.evidence_json, p.engine_config_id,"
        " p.verified_alternatives_json, p.game_id FROM position p LEFT JOIN practice_session_position sp ON sp.position_id = p.id"
        " WHERE p.id = ?", (pid,)).fetchone()
    h = P.hint_content(conn, pos, 1)
    assert h["squares"] == ["e2", "e4"] and "e4" in h["text"]
    wrong = conn.execute("UPDATE game SET pgn = '1. d4 d5 *' WHERE id = ?", (gid,))
    assert wrong is not None
    assert "No last move" in P.hint_content(conn, pos, 1)["text"]  # the game's moves do not lead to this board
