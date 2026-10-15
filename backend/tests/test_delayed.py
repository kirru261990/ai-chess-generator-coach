"""PRD v2 Step 4: the delayed assessment (scheduled 72 hours after a practice session, one waiting per type, opens exactly when due,
never holds a position the player has seen) and the Progress data (tests against the starting test, assisted practice kept apart)."""

import json
import sqlite3
from datetime import datetime, timedelta

import chess
import pytest

from app.db.schema import connect
from app.learner import assessment as A
from app.learner import practice as P
from app.learner import progress as G
from tests.test_assessment import CFG, FORBIDDEN_KEYS, T0, FakeAnalyser, keys  # noqa: F401
from tests.test_practice import at, begin, finish_session, make_store

H72 = timedelta(hours=72)


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "store.sqlite3")
    yield c
    c.close()


@pytest.fixture
def store(conn):
    return make_store(conn, practice_m1=24)  # enough for several sessions


def done_session(conn, t="M1", seconds=0):
    sid, view = begin(conn, t, seconds)
    finish_session(conn, sid, view)
    return sid


def completed_at(conn, sid):
    return datetime.fromisoformat(conn.execute("SELECT completed_at FROM practice_session WHERE id = ?", (sid,)).fetchone()[0])


def delayed_rows(conn, t="M1"):
    return conn.execute("SELECT * FROM assessment WHERE kind = 'DELAYED' AND mistake_type = ? ORDER BY id", (t,)).fetchall()


def take(conn, aid, now):
    """Answer a delayed assessment with the first legal move and 'none' everywhere, then submit it."""
    view = A.get_assessment(conn, aid, now=now)
    while view["current"]:
        cur = view["current"]
        view = A.submit_item(conn, aid, cur["ord"], "none", cur["legal_moves"][0], FakeAnalyser(), now=now + timedelta(seconds=9))
    A.submit(conn, aid, now=now + timedelta(minutes=5))


# --- scheduling --------------------------------------------------------------------------------------------------------------


def test_finishing_a_session_schedules_the_delayed_test_72_hours_after_completion(store):
    conn = store.conn
    sid = done_session(conn)
    (row,) = delayed_rows(conn)
    assert row["source_session_id"] == sid and row["status"] == "pending" and row["kind"] == "DELAYED"
    assert datetime.fromisoformat(row["due_at"]) == completed_at(conn, sid) + H72
    positions = conn.execute(
        "SELECT p.* FROM assessment_position ap JOIN position p ON p.id = ap.position_id WHERE ap.assessment_id = ? ORDER BY ap.ord",
        (row["id"],)).fetchall()
    kinds = [p["kind"] for p in positions]
    assert len(positions) == 5 and kinds.count("MISTAKE") in (3, 4)
    assert all(p["pool"] == "HELDOUT" and p["exposure_status"] == "UNSEEN" for p in positions)
    assert all(p["mistake_type"] == "M1" for p in positions if p["kind"] == "MISTAKE")
    assert P.summary(conn, sid)["delayed_test"] == {"status": "scheduled", "assessment_id": row["id"], "due_at": row["due_at"]}


def test_the_test_is_closed_until_exactly_72_hours_and_shows_nothing_before(store):
    conn = store.conn
    sid = done_session(conn)
    (row,) = delayed_rows(conn)
    due = completed_at(conn, sid) + H72
    held = [r[0] for r in conn.execute(
        "SELECT p.fen FROM assessment_position ap JOIN position p ON p.id = ap.position_id WHERE ap.assessment_id = ?", (row["id"],))]
    for now in (due - timedelta(hours=71), due - timedelta(seconds=1)):
        view = A.get_assessment(conn, row["id"], now=now)
        assert view["available"] is False and view["current"] is None and view["total"] is None and view["answered"] == 0
        assert not FORBIDDEN_KEYS & set(keys(view))
        assert not [f for f in held if f in json.dumps(view)]
        for step in (lambda n=now: A.submit_item(conn, row["id"], 0, "none", "a1a2", FakeAnalyser(), now=n),
                     lambda n=now: A.submit(conn, row["id"], now=n)):
            with pytest.raises(A.AssessmentError) as e:
                step()
            assert e.value.code == "not_due_yet"
    assert conn.execute("SELECT status FROM assessment WHERE id = ?", (row["id"],)).fetchone()[0] == "pending"  # opening it was not recorded
    opened = A.get_assessment(conn, row["id"], now=due)
    assert opened["available"] is True and opened["current"]["fen"] in held and opened["total"] == 5


def test_one_test_waits_per_type_and_the_next_session_schedules_the_next_after_it_is_taken(store):
    conn = store.conn
    first = done_session(conn, seconds=0)
    (row,) = delayed_rows(conn)
    second = done_session(conn, seconds=3000)  # finished while the first test is still waiting
    assert len(delayed_rows(conn)) == 1
    assert P.summary(conn, second)["delayed_test"]["status"] == "pending_exists"
    take(conn, row["id"], completed_at(conn, first) + H72)
    third = done_session(conn, seconds=9000)
    rows = delayed_rows(conn)
    assert len(rows) == 2 and rows[1]["source_session_id"] == third
    assert datetime.fromisoformat(rows[1]["due_at"]) == completed_at(conn, third) + H72
    assert delayed_rows(conn, "M2") == []  # the other type is separate


def test_scheduling_twice_for_one_session_makes_one_test(store):
    conn = store.conn
    sid = done_session(conn)
    again = A.schedule_delayed(conn, "M1", sid, completed_at(conn, sid))
    assert again["status"] == "scheduled" and len(delayed_rows(conn)) == 1
    with pytest.raises(sqlite3.IntegrityError):  # and the database refuses a second one
        conn.execute("INSERT INTO assessment (user, mistake_type, kind, source_session_id, created_at, due_at, status)"
                     " VALUES (?, 'M1', 'DELAYED', ?, 'x', 'x', 'submitted')", (A.user(), sid))


def test_a_delayed_test_never_holds_a_position_seen_in_practice_or_in_an_earlier_test(store):
    conn = store.conn
    seen_boards = set()
    for round_ in range(3):
        sid = done_session(conn, seconds=round_ * 9000)
        (row,) = [r for r in delayed_rows(conn) if r["source_session_id"] == sid]
        boards = {(r["game_id"], r["ply"]) for r in conn.execute(
            "SELECT p.game_id, p.ply FROM assessment_position ap JOIN position p ON p.id = ap.position_id WHERE ap.assessment_id = ?",
            (row["id"],))}
        assert len(boards) == 5 and not boards & seen_boards
        seen_boards |= boards
        take(conn, row["id"], completed_at(conn, sid) + H72)
    practised = {(r["game_id"], r["ply"]) for r in conn.execute(
        "SELECT game_id, ply FROM position WHERE exposure_status = 'PRACTICED'")}
    baseline = {(r["game_id"], r["ply"]) for r in conn.execute(
        "SELECT p.game_id, p.ply FROM assessment_position ap JOIN assessment a ON a.id = ap.assessment_id"
        " JOIN position p ON p.id = ap.position_id WHERE a.kind = 'BASELINE'")}
    assert not seen_boards & (practised | baseline)


def test_no_test_is_scheduled_when_the_pool_cannot_supply_five(store):
    conn = store.conn
    conn.execute("UPDATE position SET excluded_reason = 'used' WHERE pool = 'HELDOUT' AND kind = 'CLEAN' AND exposure_status = 'UNSEEN'")
    sid = done_session(conn)
    assert delayed_rows(conn) == []
    assert P.summary(conn, sid)["delayed_test"] == {"status": "no_positions"}


# --- the home and the missing-schedule command ---------------------------------------------------------------------------------


def test_home_shows_the_waiting_test_when_it_opens_and_how_many_are_done(store):
    conn = store.conn
    assert A.home(conn, now=T0)["types"][0]["delayed"] == {"waiting": None, "done": []}
    sid = done_session(conn)
    (row,) = delayed_rows(conn)
    due = completed_at(conn, sid) + H72
    before = A.home(conn, now=due - timedelta(minutes=1))["types"][0]["delayed"]
    assert before["waiting"] == {"assessment_id": row["id"], "status": "pending", "due_at": row["due_at"], "available": False}
    assert A.home(conn, now=due)["types"][0]["delayed"]["waiting"]["available"] is True
    take(conn, row["id"], due)
    assert A.home(conn, now=due)["types"][0]["delayed"] == {"waiting": None, "done": [row["id"]]}


def test_schedule_missing_covers_a_session_finished_before_step_4(store):
    conn = store.conn
    sid = done_session(conn)
    conn.execute("DELETE FROM assessment_position WHERE assessment_id IN (SELECT id FROM assessment WHERE kind = 'DELAYED')")
    conn.execute("DELETE FROM assessment WHERE kind = 'DELAYED'")  # as if the session had been finished before the feature existed
    out = A.schedule_delayed(conn, "M1", sid, completed_at(conn, sid))
    assert out["status"] == "scheduled" and out["due_at"] == (completed_at(conn, sid) + H72).isoformat(timespec="milliseconds")
    assert A.schedule_delayed(conn, "M1", sid, completed_at(conn, sid)) == out  # repeating changes nothing


# --- progress ----------------------------------------------------------------------------------------------------------------


def test_progress_sets_the_tests_against_the_baseline_and_keeps_practice_separate(store):
    conn = store.conn
    sid = done_session(conn)
    (row,) = delayed_rows(conn)
    take(conn, row["id"], completed_at(conn, sid) + H72)
    p = {t["mistake_type"]: t for t in G.progress(conn)["types"]}["M1"]
    assert p["baseline"]["total"] == 5 and p["baseline"]["kind"] == "BASELINE" and len(p["delayed"]) == 1
    d = p["delayed"][0]
    assert d["kind"] == "DELAYED" and d["total"] == 5 and set(d["scores"]) == {"recognition", "move", "combined"}
    assert d["chance_pending"] is True  # the guessing numbers are worked out in the background
    comp = p["comparison"]
    assert comp["comparable"] == {"move": True, "recognition": True}  # both are question version 2
    assert comp["baseline"]["total"] == 5 and comp["delayed"][0]["assessment_id"] == d["assessment_id"]
    expected = round((d["scores"]["move"] / 5 - p["baseline"]["scores"]["move"] / 5) * 5, 1)
    assert comp["gain_move_positions_of_5"] == expected
    pr = p["practice"]
    assert pr["assisted"] is True and pr["sessions"] == 1 and pr["positions"] == 5 and pr["first_attempts"] == 5
    assert pr["first_attempt_correct"] == 5 and pr["attempts_with_hint"] == 0 and pr["attempts"] == 5 and pr["reasons"] == []
    # the other type has neither a delayed test nor practice
    other = {t["mistake_type"]: t for t in G.progress(conn)["types"]}["M2"]
    assert other["delayed"] == [] and other["comparison"] is None and other["practice"]["sessions"] == 0


def test_a_version_1_baseline_is_compared_on_the_move_score_only(store):
    conn = store.conn
    conn.execute("UPDATE assessment SET question_version = '1' WHERE kind = 'BASELINE' AND mistake_type = 'M1'")
    sid = done_session(conn)
    (row,) = delayed_rows(conn)
    take(conn, row["id"], completed_at(conn, sid) + H72)
    comp = {t["mistake_type"]: t for t in G.progress(conn)["types"]}["M1"]["comparison"]
    assert comp["comparable"] == {"move": True, "recognition": False}
    assert comp["delayed"][0]["recognition"] is None and comp["delayed"][0]["combined"] is None
    assert "gain_move_positions_of_5" in comp and "gain_combined_positions_of_5" not in comp


def test_a_set_aside_baseline_is_not_the_baseline_in_progress(store):
    conn = store.conn
    first = conn.execute("SELECT id FROM assessment WHERE kind = 'BASELINE' AND mistake_type = 'M1'").fetchone()[0]
    A.supersede_baseline(conn, first, "retake")
    p = {t["mistake_type"]: t for t in G.progress(conn)["types"]}["M1"]
    assert p["baseline"] is None and p["set_aside"] == 1


def test_practice_stats_count_hints_retries_and_reasons(store):
    from tests.test_practice import play

    conn = store.conn
    sid, view = begin(conn)
    fb = play(conn, sid, view, good=False, hints=2, clock=0)  # a hint and a move that leaves the rook
    view = P.next_position(conn, sid, fb["current"]["ord"], now=at(40))
    pr = {t["mistake_type"]: t for t in G.progress(conn)["types"]}["M1"]["practice"]
    assert pr["first_attempts"] == 1 and pr["first_attempt_correct"] == 0 and pr["assisted_correct"] == 0
    assert pr["attempts_with_hint"] == 1 and pr["not_sound"] == 1 and view["status"] == "in_progress"
    assert sum(r["count"] for r in pr["reasons"]) == pr["not_sound"]  # one main reason per not-sound try: the counts add up
    assert pr["reasons"][0]["reason"] == "the piece was still in danger after the move"
    assert pr["sessions"] == 0  # not finished yet


# --- over HTTP ---------------------------------------------------------------------------------------------------------------


def test_http_the_delayed_test_is_closed_then_open_and_progress_leaks_nothing(store, tmp_path, monkeypatch):
    from contextlib import contextmanager

    from fastapi.testclient import TestClient

    from app.api import coach
    from app.api.main import app

    conn = store.conn

    @contextmanager
    def fake_open(_c):
        yield FakeAnalyser()

    db_path = tmp_path / "store.sqlite3"
    monkeypatch.setattr(coach, "DB_PATH", db_path)
    monkeypatch.setattr(coach, "open_analyser", fake_open)
    monkeypatch.setattr(coach, "start_chance_job", lambda ids: None)
    client = TestClient(app)
    sid = done_session(conn)
    (row,) = delayed_rows(conn)
    held = [r[0] for r in conn.execute(
        "SELECT p.fen FROM assessment_position ap JOIN position p ON p.id = ap.position_id WHERE ap.assessment_id = ?", (row["id"],))]
    home = client.get("/coach/home").json()["types"][0]["delayed"]["waiting"]
    assert home["assessment_id"] == row["id"] and home["available"] is False  # real time: three days away
    closed = client.get(f"/coach/assessments/{row['id']}")
    assert closed.status_code == 200 and closed.json()["available"] is False and closed.json()["current"] is None
    assert client.post(f"/coach/assessments/{row['id']}/items", json={"ord": 0, "recognition": "none", "move": "a1a2"}).status_code == 403
    bodies = [closed.json(), client.get("/coach/home").json(), client.get("/coach/progress").json(),
              client.get(f"/coach/practice/sessions/{sid}/summary").json()]
    text = json.dumps(bodies)
    assert not [f for f in held if f'"{f}"' in text]  # a delayed test's boards appear nowhere before it opens
    assert bodies[3]["delayed_test"]["status"] == "scheduled"
    waiting = client.get("/coach/progress").json()["types"][0]["waiting"]
    assert waiting["assessment_id"] == row["id"] and waiting["available"] is False
    conn.execute("UPDATE assessment SET due_at = ? WHERE id = ?", ((datetime.fromisoformat(row["due_at"]) - H72 - H72).isoformat(), row["id"]))
    opened = client.get(f"/coach/assessments/{row['id']}").json()
    assert opened["available"] is True and opened["current"]["fen"] in held and chess.Board(opened["current"]["fen"])


def test_each_not_sound_move_has_one_main_reason_in_a_fixed_order():
    assert G.main_reason({"failed": ["refutation_still_wins", "eval_loss_too_large"]}) == "refutation_still_wins"
    assert G.main_reason({"failed": ["free_piece_not_taken", "eval_loss_too_large"]}) == "free_piece_not_taken"
    assert G.main_reason({"failed": ["eval_loss_too_large"], "mate": "allowed"}) == "allows_checkmate"
    assert G.main_reason({"failed": ["eval_loss_too_large"], "mate": "missed"}) == "missed_checkmate"
    assert G.main_reason({"failed": ["eval_loss_too_large"], "mate": None}) == "eval_loss_too_large"
    assert G.main_reason({"failed": []}) is None


# --- review on PR 74: choose the mix from what the pool can actually supply ----------------------------------------------------


def _pool(conn, mistakes, cleans):
    """A held-out pool with exactly this many unused M1 mistake and CLEAN positions."""
    from tests.test_assessment import Store

    s = Store(conn)
    for _ in range(mistakes):
        s.position("M1")
    for _ in range(cleans):
        s.position("CLEAN")
    return s


@pytest.mark.parametrize(("mistakes", "cleans", "expected"), [
    (3, 2, (3, 2)),   # only 3+2 exists: asking for 4 mistakes used to return 4 positions and "no positions left"
    (4, 1, (4, 1)),   # only 4+1 exists
    (5, 5, None),     # both exist: the mix is chosen at random
])
def test_the_mix_is_chosen_from_what_the_pool_can_supply(conn, mistakes, cleans, expected):
    import random

    _pool(conn, mistakes, cleans)
    seen = set()
    for seed in range(40):
        chosen = A._allocate(conn, "M1", random.Random(seed))
        assert len(chosen) == A.SIZE, f"seed {seed} gave {len(chosen)} positions"
        n_mistakes = sum(1 for r in chosen if conn.execute("SELECT kind FROM position WHERE id = ?", (r["id"],)).fetchone()[0] == "MISTAKE")
        seen.add((n_mistakes, A.SIZE - n_mistakes))
    assert seen == ({expected} if expected else {(3, 2), (4, 1)})


@pytest.mark.parametrize(("mistakes", "cleans"), [(2, 9), (9, 0), (0, 0), (2, 2), (3, 1), (4, 0)])
def test_nothing_is_allocated_when_no_valid_mix_exists(conn, mistakes, cleans):
    import random

    _pool(conn, mistakes, cleans)
    assert all(A._allocate(conn, "M1", random.Random(seed)) == [] for seed in range(10))


def test_the_last_delayed_test_is_still_scheduled_when_the_pool_is_at_its_edge(store):
    """Seen end to end: leave exactly 3 unused mistake and 2 clean positions and finish a session."""
    conn = store.conn
    keep_m = [r[0] for r in conn.execute(
        "SELECT id FROM position WHERE pool = 'HELDOUT' AND kind = 'MISTAKE' AND mistake_type = 'M1' AND exposure_status = 'UNSEEN'"
        " AND retired_at IS NULL AND json_extract(evidence_json, '$.lost_piece') = 'other' ORDER BY id LIMIT 3")]
    keep_c = [r[0] for r in conn.execute(
        "SELECT id FROM position WHERE pool = 'HELDOUT' AND kind = 'CLEAN' AND exposure_status = 'UNSEEN' AND retired_at IS NULL"
        " ORDER BY id LIMIT 2")]
    keep = set(keep_m + keep_c)
    for (pid,) in conn.execute("SELECT id FROM position WHERE pool = 'HELDOUT' AND exposure_status = 'UNSEEN'").fetchall():
        if pid not in keep:
            conn.execute("UPDATE position SET excluded_reason = 'used' WHERE id = ?", (pid,))
    sid = done_session(conn)
    (row,) = delayed_rows(conn)
    assert row["source_session_id"] == sid
    assert P.summary(conn, sid)["delayed_test"]["status"] == "scheduled"
