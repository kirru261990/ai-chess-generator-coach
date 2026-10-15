"""PRD v2 Step 2: the pool check, the baseline assessment (allocation, answers, timing, final submit, reveal, scoring with
random-guess rates) and the frozen real-game window. The engine is scripted: every move scores 0, so a move is unsound only
by the refutation rule, which these tests set up on real boards."""

import json
import random
import sqlite3
from datetime import UTC, datetime, timedelta

import chess
import pytest

from app.db.schema import connect
from app.engine.evidence import EngineConfig, EvidenceAnalysis, Line, register_config
from app.learner import assessment as A
from app.learner import realgame

CFG = EngineConfig("Stockfish 19", "nn-test.nnue", "sha", depth=18, multipv=3, hash_mb=64, threads=1)
T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

# Boards. The full-move number makes every stored FEN unique, so a test can look for a board in a response.
# M1, left in danger: White's rook on h7 is attacked by the queen and not defended. Target h7.
M1_FEN = "4k3/4q2R/8/8/8/8/3B4/6K1 w - - 0 {n}"
# M2: Black's queen on d5 can be taken for free by the rook on d2. Target d5.
M2_FEN = "4k3/8/8/3q4/8/8/3R4/6K1 w - - 0 {n}"
# CLEAN: nothing is attacked and nothing can be won.
CLEAN_FEN = "4k3/8/8/8/8/8/3B4/4K3 w - - 0 {n}"
FORBIDDEN_KEYS = {"kind", "best_move", "eval", "eval_before", "eval_after", "eval_loss", "refutation_line", "target_squares",
                  "answer_squares", "evidence", "evidence_json", "verified_alternatives", "good_moves", "line", "move_sound",
                  "recognition_correct", "tap_correct", "correct", "explanation", "material_swing", "player_move",
                  "game_move", "pool"}


class FakeAnalyser:
    """Any position: the first legal move (UCI order) is best and every line scores 0 cp."""

    config = CFG

    def __init__(self, config=CFG):
        self.config = config
        self.calls = 0

    def analyse(self, board, depth=None):
        self.calls += 1
        moves = sorted(m.uci() for m in board.legal_moves)[:3]
        return EvidenceAnalysis(board.fen(), self.config.id, tuple(Line(m, (m,), 0, None, None, 18) for m in moves))


def evidence(kind, fen, n):
    board = chess.Board(fen)
    if kind == "CLEAN":
        return {"kind": "CLEAN", "fen": fen, "ply": 20, "player_move": {"uci": "e1f1", "san": "Kf1"},
                "best_move": {"uci": "e1f1", "san": "Kf1"}, "attacked_squares": [], "engine_config_id": CFG.id}
    if kind == "M1":
        return {"mistake_type": "M1", "fen": fen, "ply": 20, "player_move": {"uci": "g1g2", "san": "Kg2"},
                "best_move": {"uci": "h7h1", "san": "Rh1"}, "target_squares": ["h7"], "lost_piece": "other",
                "refutation_line": {"uci": ["e7h7"], "san": ["Qxh7"]}, "material_swing": 5,
                "eval_before": 0, "eval_after": -500, "eval_loss": 500, "engine_config_id": CFG.id}
    return {"mistake_type": "M2", "fen": fen, "ply": 20, "player_move": {"uci": "g1g2", "san": "Kg2"},
            "best_move": {"uci": "d2d5", "san": "Rxd5"}, "target_squares": ["d5"],
            "free_captures": [{"uci": "d2d5", "san": "Rxd5"}],
            "refutation_line": {"uci": ["d2d5"], "san": [board.san(chess.Move.from_uci("d2d5"))]},
            "material_swing": 9, "eval_before": 900, "eval_after": 0, "eval_loss": 900, "engine_config_id": CFG.id}


class Store:
    """A temporary store with games and positions, numbered so each board is unique."""

    def __init__(self, conn):
        self.conn = conn
        self.n = 0
        register_config(conn, CFG)

    def game(self, pool, tc="600", played_at=0):
        self.n += 1
        gid = f"chesscom:g{self.n}"
        self.conn.execute(
            "INSERT INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
            " VALUES (?, 'chesscom', ?, 'white', ?, ?, ?, '')",
            (gid, f"g{self.n}", tc, played_at or self.n, pool),
        )
        return gid

    def position(self, kind, pool="HELDOUT", game_id=None, ply=20, lost_piece="other", fen=None):
        game_id = game_id or self.game(pool)
        self.n += 1
        template = {"M1": M1_FEN, "M2": M2_FEN, "CLEAN": CLEAN_FEN}[kind]
        fen = fen or template.format(n=self.n)
        ev = evidence(kind, fen, self.n)
        if kind == "M1":
            ev["lost_piece"] = lost_piece
        alternatives = None if kind == "CLEAN" else json.dumps([ev["best_move"]])
        return self.conn.execute(
            "INSERT INTO position (game_id, ply, fen, kind, mistake_type, source_tag, pool, original_move, evidence_json,"
            " verified_alternatives_json, engine_config_id, detector_version) VALUES (?, ?, ?, ?, ?, 'chesscom', ?, ?, ?, ?, ?, 'v')",
            (game_id, ply, fen, "CLEAN" if kind == "CLEAN" else "MISTAKE", None if kind == "CLEAN" else kind, pool,
             ev["player_move"]["uci"], json.dumps(ev), alternatives, CFG.id),
        ).lastrowid

    def fill(self, m1=16, m2=16, clean=12):
        for _ in range(m1):
            self.position("M1")
        for _ in range(m2):
            self.position("M2")
        for _ in range(clean):
            self.position("CLEAN")


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "store.sqlite3")
    yield c
    c.close()


@pytest.fixture
def store(conn):
    s = Store(conn)
    s.fill()
    return s


def keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys(v)


def start(conn, t="M1", seed=1):
    return A.start_baseline(conn, t, rng=random.Random(seed), now=T0)["assessment_id"]


def allocated(conn, aid):
    return conn.execute(
        "SELECT p.* FROM assessment_position ap JOIN position p ON p.id = ap.position_id WHERE ap.assessment_id = ?"
        " ORDER BY ap.ord", (aid,)).fetchall()


def answer(conn, aid, view, good=True, now=None, analyser=None):
    """Answer the current board: the right tap and a sound move when `good`, else a wrong tap and an unsound move."""
    cur = view["current"]
    pos = conn.execute(
        "SELECT kind, mistake_type FROM position p JOIN assessment_position ap ON ap.position_id = p.id"
        " WHERE ap.assessment_id = ? AND ap.ord = ?", (aid, cur["ord"])).fetchone()
    kind = pos["mistake_type"] or "CLEAN"
    tap, move = {
        ("M1", True): ("h7", "h7h1"), ("M1", False): ("d2", "g1f1"),
        ("M2", True): ("d5", "d2d5"), ("M2", False): ("d2", "g1f1"),
        ("CLEAN", True): ("none", "e1f1"), ("CLEAN", False): ("d2", "e1f1"),
    }[(kind, good)]
    return A.submit_item(conn, aid, cur["ord"], tap, move, analyser or FakeAnalyser(), now=now or T0 + timedelta(seconds=7))


# --- pool check ----------------------------------------------------------------------------------------------------------


def test_pool_check_counts_only_assessable_heldout_positions(conn):
    s = Store(conn)
    s.fill(m1=15, m2=0, clean=8)
    s.position("M1", lost_piece="moved")  # decision 14: nothing to tap before the move
    s.position("M1", pool="PRACTICE")
    seen = s.position("M1")
    conn.execute("UPDATE position SET excluded_reason = 'shown_in_explorer' WHERE id = ?", (seen,))
    retired = s.position("M1")
    conn.execute("UPDATE position SET retired_at = 'x' WHERE id = ?", (retired,))
    status = A.pool_status(conn, "M1")
    assert status["mistake_positions"] == 15 and status["clean_positions"] == 8 and not status["ready"]
    with pytest.raises(A.AssessmentError) as e:
        A.start_baseline(conn, "M1")
    assert e.value.code == "pool_too_small" and "15 of 16" in str(e.value)
    s.position("M1")
    assert A.pool_status(conn, "M1")["ready"]


def test_a_seen_sibling_board_is_not_assessable(conn):
    s = Store(conn)
    gid = s.game("HELDOUT")
    m1 = s.position("M1", game_id=gid)
    s.position("M2", game_id=gid)  # same game and ply: the same board
    conn.execute("UPDATE position SET excluded_reason = 'hand_checked' WHERE id = ?", (m1,))
    assert A.pool_status(conn, "M2")["mistake_positions"] == 0


def test_home_lists_both_types_with_counts_and_baseline_status(store):
    h = A.home(store.conn)
    assert [t["mistake_type"] for t in h["types"]] == ["M1", "M2"]
    assert all(t["pool"]["ready"] and t["baseline"] is None for t in h["types"])
    aid = start(store.conn)
    assert A.home(store.conn)["types"][0]["baseline"] == {"assessment_id": aid, "status": "pending"}


# --- allocation ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(6))
def test_baseline_allocates_five_unseen_heldout_positions_of_the_right_mix(store, seed):
    aid = start(store.conn, "M2", seed)
    rows = allocated(store.conn, aid)
    kinds = [r["kind"] for r in rows]
    assert len(rows) == 5 and kinds.count("MISTAKE") in (3, 4)
    assert all(r["pool"] == "HELDOUT" and r["exposure_status"] == "UNSEEN" for r in rows)
    assert all(r["mistake_type"] == "M2" for r in rows if r["kind"] == "MISTAKE")
    assert len({r["game_id"] for r in rows}) == 5  # different games


def test_order_is_random(store):
    orders = set()
    for seed in range(8):
        conn = connect(":memory:")
        s = Store(conn)
        s.fill()
        orders.add(tuple(r["kind"] for r in allocated(conn, start(conn, "M1", seed))))
    assert len(orders) > 1


def test_start_resumes_the_open_baseline_and_refuses_a_second_one(store):
    aid = start(store.conn)
    assert A.start_baseline(store.conn, "M1") == {"assessment_id": aid, "resumed": True}
    finish(store.conn, aid)
    with pytest.raises(A.AssessmentError) as e:
        A.start_baseline(store.conn, "M1")
    assert e.value.code == "baseline_done"
    assert A.start_baseline(store.conn, "M2")["resumed"] is False  # the other type is separate


def test_unknown_type_is_refused(store):
    with pytest.raises(A.AssessmentError) as e:
        A.start_baseline(store.conn, "M3")
    assert e.value.code == "unknown_mistake_type"


# --- taking it: nothing leaks before the final submit --------------------------------------------------------------------


def test_views_before_submit_show_only_the_current_board(store):
    conn = store.conn
    aid = start(conn)
    fens = [r["fen"] for r in allocated(conn, aid)]
    view = A.get_assessment(conn, aid, now=T0)
    for i in range(5):
        assert not FORBIDDEN_KEYS & set(keys(view)), FORBIDDEN_KEYS & set(keys(view))
        text = json.dumps(view)
        assert view["current"]["fen"] == fens[i]
        assert [f for f in fens if f in text] == [fens[i]]  # no other board, earlier or later
        assert view["current"]["legal_moves"] == sorted(m.uci() for m in chess.Board(fens[i]).legal_moves)
        view = answer(conn, aid, view, good=i % 2 == 0)
        if i < 4:
            assert view["answered"] == i + 1
    assert view["current"] is None and view["ready_to_submit"]
    assert not FORBIDDEN_KEYS & set(keys(view))
    with pytest.raises(A.AssessmentError) as e:
        A.results(conn, aid)
    assert e.value.code == "not_submitted"


def test_answers_are_checked_and_cannot_be_changed(store):
    conn = store.conn
    aid = start(conn)
    view = A.get_assessment(conn, aid, now=T0)
    cur = view["current"]
    for ord_, tap, move, code in [
        (cur["ord"] + 1, "none", cur["legal_moves"][0], "not_current_position"),
        (cur["ord"], "e4", cur["legal_moves"][0], "tap_a_piece"),  # an empty square
        (cur["ord"], "zz", cur["legal_moves"][0], "tap_a_piece"),
        (cur["ord"], "none", "a1a8", "illegal_move"),
        (cur["ord"], "none", "nonsense", "illegal_move"),
    ]:
        with pytest.raises(A.AssessmentError) as e:
            A.submit_item(conn, aid, ord_, tap, move, FakeAnalyser())
        assert e.value.code == code
    answer(conn, aid, view)
    with pytest.raises(A.AssessmentError) as e:  # the same board again: already answered
        A.submit_item(conn, aid, cur["ord"], "none", cur["legal_moves"][0], FakeAnalyser())
    assert e.value.code == "not_current_position"


def test_submit_needs_every_answer(store):
    aid = start(store.conn)
    with pytest.raises(A.AssessmentError) as e:
        A.submit(store.conn, aid)
    assert e.value.code == "not_finished"


def test_a_different_engine_config_is_refused_not_compared(store):
    aid = start(store.conn)
    view = A.get_assessment(store.conn, aid, now=T0)
    other = FakeAnalyser(EngineConfig("Stockfish 19", "nn-test.nnue", "another-binary", 18, 3, 64, 1))
    with pytest.raises(A.AssessmentError) as e:
        answer(store.conn, aid, view, analyser=other)
    assert e.value.code == "engine_config_changed"


# --- timing ----------------------------------------------------------------------------------------------------------------


def result_rows(conn, aid):
    return conn.execute(
        "SELECT r.* FROM assessment_result r JOIN assessment_position ap USING (assessment_id, position_id)"
        " WHERE r.assessment_id = ? ORDER BY ap.ord", (aid,)).fetchall()


def test_the_server_times_each_decision_and_caps_it(store):
    conn = store.conn
    aid = start(conn)
    view = A.get_assessment(conn, aid, now=T0)
    view = answer(conn, aid, view, now=T0 + timedelta(seconds=42))  # next board shown at +42 s
    view = answer(conn, aid, view, now=T0 + timedelta(seconds=42 + 400))  # over the cap
    rows = result_rows(conn, aid)
    assert rows[0]["elapsed_ms"] == 42_000 and not rows[0]["interrupted"]
    assert rows[1]["elapsed_ms"] == A.TIME_CAP_MS and rows[1]["interrupted"]


def test_a_board_shown_again_later_is_flagged_interrupted_but_a_quick_repeat_is_not(store):
    conn = store.conn
    aid = start(conn)
    A.get_assessment(conn, aid, now=T0)
    view = A.get_assessment(conn, aid, now=T0 + timedelta(seconds=1))  # the page asked twice
    view = answer(conn, aid, view, now=T0 + timedelta(seconds=5))
    A.get_assessment(conn, aid, now=T0 + timedelta(seconds=60))  # left and resumed: same board again
    view = answer(conn, aid, view, now=T0 + timedelta(seconds=90))
    rows = result_rows(conn, aid)
    assert not rows[0]["interrupted"]
    assert rows[1]["interrupted"] and rows[1]["elapsed_ms"] == 85_000


# --- final submit and reveal -------------------------------------------------------------------------------------------


def finish(conn, aid, good=(True, True, True, True, True)):
    view = A.get_assessment(conn, aid, now=T0)
    for g in good:
        view = answer(conn, aid, view, good=g)
    return A.submit(conn, aid, now=T0 + timedelta(minutes=5))


def test_submit_marks_positions_tested_and_they_are_never_allocated_again(store):
    conn = store.conn
    before = A.pool_status(conn, "M1")
    aid = start(conn)
    finish(conn, aid)
    rows = allocated(conn, aid)
    assert all(r["exposure_status"] == "TESTED" for r in rows)
    after = A.pool_status(conn, "M1")
    n_mistakes = sum(r["kind"] == "MISTAKE" for r in rows)
    assert after["mistake_positions"] == before["mistake_positions"] - n_mistakes
    assert after["clean_positions"] == before["clean_positions"] - (5 - n_mistakes)
    m2 = start(conn, "M2")
    assert not {r["id"] for r in rows} & {r["id"] for r in allocated(conn, m2)}
    assert A.submit(conn, aid) == {"assessment_id": aid, "status": "submitted"}  # submitting again changes nothing
    with pytest.raises(A.AssessmentError) as e:
        A.submit_item(conn, aid, 0, "none", "e1f1", FakeAnalyser())
    assert e.value.code == "assessment_submitted"


def test_the_sibling_row_of_an_assessed_board_is_never_allocated(conn):
    s = Store(conn)
    gid = s.game("HELDOUT")
    m1 = s.position("M1", game_id=gid)
    m2 = s.position("M2", game_id=gid)
    aid = conn.execute("INSERT INTO assessment (user, mistake_type, kind, created_at, due_at, status)"
                       " VALUES ('u', 'M1', 'BASELINE', 'x', 'x', 'pending')").lastrowid
    conn.execute("INSERT INTO assessment_position VALUES (?, ?, 0)", (aid, m1))
    other = conn.execute("INSERT INTO assessment (user, mistake_type, kind, created_at, due_at, status)"
                         " VALUES ('u', 'M2', 'BASELINE', 'x', 'x', 'pending')").lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="assessed once"):
        conn.execute("INSERT INTO assessment_position VALUES (?, ?, 0)", (other, m2))
    assert A.pool_status(conn, "M2")["mistake_positions"] == 0


def test_results_score_each_part_and_explain_from_the_evidence(store):
    conn = store.conn
    aid = start(conn)
    finish(conn, aid, good=(True, False, True, False, True))
    r = A.results(conn, aid)
    items = r["items"]
    assert [i["correct"] for i in items] == [True, False, True, False, True]
    assert r["scores"] == {"recognition": 3, "move": 3 + sum(1 for i in items[1::2] if i["kind"] == "CLEAN"),
                           "combined": 3}
    for i in items:
        if i["kind"] == "MISTAKE":
            assert i["answer_squares"] == ["h7"] and "rook on h7" in i["explanation"] and "take it with Qxh7" in i["explanation"]
            assert i["good_moves"] == [{"uci": "h7h1", "san": "Rh1"}]
            assert i["move_sound"] == (i["your_move"]["uci"] == "h7h1")
            if not i["move_sound"]:
                assert "could still win the piece" in i["move_explanation"]
        else:
            assert i["answer_squares"] == [] and "No immediate threat" in i["explanation"]
        assert not i["interrupted"]
    assert items[0]["seconds"] == 7  # answered 7 s after it was shown; the next board was shown at that moment


def test_random_guess_rates(store):
    conn = store.conn
    aid = start(conn)
    finish(conn, aid)
    r = A.results(conn, aid)
    assert r["chance_pending"] and r["chance"]["move"] is None
    # recognition: right answers / (pieces + 1): M1 board has 5 pieces, CLEAN board 3
    expected = sum(1 / 6 if i["kind"] == "MISTAKE" else 1 / 4 for i in r["items"])
    assert r["chance"]["recognition"] == round(expected, 2)
    pending = A.missing_move_chances(conn, aid)
    assert len(pending) == 5
    for pid in pending:
        A.compute_move_chance(conn, pid, FakeAnalyser())
    r = A.results(conn, aid)
    assert not r["chance_pending"] and A.missing_move_chances(conn, aid) == []
    for i in r["items"]:
        board = chess.Board(i["fen"])
        legal = board.legal_moves.count()
        if i["kind"] == "CLEAN":
            assert i["move_chance"] == 1.0  # every move scores 0 here, so every move is sound
        else:  # the sound moves are the ones that stop the refutation winning the piece
            sound_moves = [m for m in board.legal_moves
                           if A.judge(board, m, "MISTAKE", json.loads(conn.execute(
                               "SELECT evidence_json FROM position WHERE fen = ?", (i["fen"],)).fetchone()[0]),
                               FakeAnalyser()).sound]
            assert i["move_chance"] == len(sound_moves) / legal
            assert 0 < len(sound_moves) < legal
    assert r["chance"]["move"] == round(sum(i["move_chance"] for i in r["items"]), 2)
    assert r["chance"]["combined"] == round(sum(i["move_chance"] * i["recognition_chance"] for i in r["items"]), 2)


def test_move_chance_is_computed_once(store):
    conn = store.conn
    pid = store.position("CLEAN")
    first = FakeAnalyser()
    A.compute_move_chance(conn, pid, first)
    again = FakeAnalyser()
    A.compute_move_chance(conn, pid, again)
    assert first.calls > 0 and again.calls == 0


# --- the frozen real-game window (PRD §8) --------------------------------------------------------------------------------


def test_baseline_window_freezes_the_last_30_games_per_time_control_once(conn):
    s = Store(conn)
    t0 = int(T0.timestamp())
    ten = [s.game("PRACTICE" if i % 2 else "HELDOUT", "600", t0 - 1000 + i) for i in range(35)]
    fifteen = [s.game("HELDOUT", "900+10", t0 - 1000 + i) for i in range(12)]
    s.game("PRACTICE", "600", t0 + 5)  # played after the freeze
    windows = realgame.freeze_baseline_window(conn, "M1", now=T0)
    by_tc = {w["time_control"]: w["game_ids"] for w in windows}
    assert by_tc["600"] == list(reversed(ten))[:30]  # newest first, both pools
    assert by_tc["900+10"] == list(reversed(fifteen))
    s.game("PRACTICE", "600", t0 - 1)
    again = realgame.freeze_baseline_window(conn, "M1", now=T0 + timedelta(days=3))
    assert again == windows  # never changes
    assert realgame.frozen_windows(conn, "M2") == []
    with pytest.raises(sqlite3.IntegrityError, match="never edited"):
        conn.execute("UPDATE baseline_window SET game_ids_json = '[]'")
