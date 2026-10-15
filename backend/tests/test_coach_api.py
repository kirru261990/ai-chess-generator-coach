"""PRD v2 Step 2 exit gate over HTTP: a baseline assessment works end to end, and held-out positions never leave the
assessment endpoints (PRD §5.3, §11). The engine is scripted (`FakeAnalyser`) and the store is a temporary file."""

import ast
import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import coach
from app.api.main import app
from app.db.schema import connect
from app.learner import assessment as A
from tests.test_assessment import FORBIDDEN_KEYS, T0, FakeAnalyser, Store, finish, keys

client = TestClient(app)
APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "store.sqlite3"
    conn = connect(path)
    s = Store(conn)
    s.fill()
    for _ in range(3):
        s.position("M1", pool="PRACTICE")
        s.position("CLEAN", pool="PRACTICE")

    @contextmanager
    def fake_open(_conn):
        yield FakeAnalyser()

    jobs = []
    monkeypatch.setattr(coach, "DB_PATH", path)
    monkeypatch.setattr(coach, "open_analyser", fake_open)
    monkeypatch.setattr(coach, "start_chance_job", lambda ids: jobs.append(list(ids)))
    s.jobs = jobs
    yield s
    conn.close()


def heldout_fens(conn):
    return [r[0] for r in conn.execute("SELECT fen FROM position WHERE pool = 'HELDOUT'")]


def tap_and_move(conn, assessment_id, current):
    """The right answer for the board on screen (looked up in the store, as the test knows the answers)."""
    kind = conn.execute(
        "SELECT IFNULL(p.mistake_type, 'CLEAN') FROM position p JOIN assessment_position ap ON ap.position_id = p.id"
        " WHERE ap.assessment_id = ? AND ap.ord = ?", (assessment_id, current["ord"])).fetchone()[0]
    return {"M1": ("h7", "h7h1"), "M2": ("d5", "d2d5"), "CLEAN": ("none", "e1f1")}[kind]


def test_a_baseline_works_end_to_end_and_reveals_nothing_before_the_final_submit(store):
    conn = store.conn
    home = client.get("/coach/home").json()
    assert [t["pool"]["ready"] for t in home["types"]] == [True, True]
    started = client.post("/coach/assessments/baseline", json={"mistake_type": "M1"}).json()
    aid = started["assessment_id"]
    assert started["resumed"] is False
    assert len(store.jobs) == 1 and len(store.jobs[0]) == 5  # random-guess rates start computing at once
    fens = [r[0] for r in conn.execute(
        "SELECT p.fen FROM assessment_position ap JOIN position p ON p.id = ap.position_id WHERE assessment_id = ?"
        " ORDER BY ord", (aid,))]

    responses = [started]
    view = client.get(f"/coach/assessments/{aid}").json()
    for i in range(5):
        responses.append(view)
        assert view["current"]["fen"] == fens[i]
        early = client.get(f"/coach/assessments/{aid}/results")
        assert early.status_code == 403 and early.json()["error"] == "not_submitted"
        responses.append(early.json())
        tap, move = tap_and_move(conn, aid, view["current"])
        r = client.post(f"/coach/assessments/{aid}/items", json={"ord": view["current"]["ord"], "recognition": tap,
                                                                 "move": move})
        assert r.status_code == 200
        view = r.json()
    responses.append(view)
    assert view["ready_to_submit"]
    for body in responses:
        assert not FORBIDDEN_KEYS & set(keys(body)), body
    # each board appears only while it is the board on screen
    for body in responses:
        shown = (body.get("current") or {}).get("fen")
        assert [f for f in fens if f in json.dumps(body)] == ([shown] if shown else [])

    done = client.post(f"/coach/assessments/{aid}/submit").json()
    assert done["scores"] == {"recognition": 5, "move": 5, "combined": 5}
    assert done["chance_pending"] and done["chance"]["recognition"] > 0
    assert [i["fen"] for i in done["items"]] == fens
    assert client.get(f"/coach/assessments/{aid}/results").json()["scores"] == done["scores"]
    status = client.get("/coach/home").json()["types"][0]["baseline"]
    assert status == {"assessment_id": aid, "status": "submitted"}
    again = client.post("/coach/assessments/baseline", json={"mistake_type": "M1"})
    assert again.status_code == 409 and again.json()["error"] == "baseline_done"


def test_errors_use_stable_codes(store):
    assert client.get("/coach/assessments/999").status_code == 404
    r = client.post("/coach/assessments/baseline", json={"mistake_type": "M9"})
    assert r.status_code == 400 and r.json()["error"] == "unknown_mistake_type"
    aid = client.post("/coach/assessments/baseline", json={"mistake_type": "M2"}).json()["assessment_id"]
    cur = client.get(f"/coach/assessments/{aid}").json()["current"]
    r = client.post(f"/coach/assessments/{aid}/items", json={"ord": cur["ord"], "recognition": "none", "move": "a1a8"})
    assert r.status_code == 400 and r.json()["error"] == "illegal_move"
    r = client.post(f"/coach/assessments/{aid}/submit")
    assert r.status_code == 409 and r.json()["error"] == "not_finished"


def test_a_small_pool_shows_counts_and_blocks(tmp_path, monkeypatch):
    path = tmp_path / "small.sqlite3"
    s = Store(connect(path))
    s.fill(m1=3, m2=0, clean=2)
    monkeypatch.setattr(coach, "DB_PATH", path)
    m1 = client.get("/coach/home").json()["types"][0]["pool"]
    assert m1 == {"mistake_positions": 3, "clean_positions": 2, "needed_mistake_positions": 16,
                  "needed_clean_positions": 8, "ready": False}
    r = client.post("/coach/assessments/baseline", json={"mistake_type": "M1"})
    assert r.status_code == 409 and r.json()["error"] == "pool_too_small"
    assert "Not enough games yet" in r.json()["message"]


def test_heldout_boards_never_leave_the_assessment_endpoints(store):
    """Every route that takes no path parameter, plus the coach home, is called with a store full of held-out boards:
    none of them may appear. Only `/coach/assessments/...` may return one."""
    fens = heldout_fens(store.conn)
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None or "{" in path or "GET" not in getattr(route, "methods", ()):
            continue
        if path.startswith("/coach/assessments") or path in ("/docs", "/redoc", "/openapi.json"):
            continue
        body = client.get(path).text
        assert not [f for f in fens if f in body], path
    body = client.get("/coach/home").text
    assert not [f for f in fens if f in body]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
    return out


def test_only_the_coach_routes_reach_the_position_store():
    """Static guard: in the API and the MCP server, only `api/coach.py` imports the store or the assessment service."""
    store_modules = {"app.db", "app.db.schema", "app.learner.assessment", "app.learner.realgame", "app.learner.practice"}
    offenders = []
    for path in sorted([*(APP_DIR / "api").glob("*.py"), *(APP_DIR / "mcp").glob("*.py")]):
        if path.name == "coach.py":
            continue
        if _imports(path) & store_modules:
            offenders.append(path.name)
    assert offenders == []


def test_practice_positions_are_never_allocated(store):
    aid = A.start_baseline(store.conn, "M1")["assessment_id"]
    pools = {r[0] for r in store.conn.execute(
        "SELECT p.pool FROM assessment_position ap JOIN position p ON p.id = ap.position_id WHERE assessment_id = ?", (aid,))}
    assert pools == {"HELDOUT"}


# --- Replay My Mistakes over HTTP (PRD v2 §6.5, §11) -------------------------------------------------------------------------

PRACTICE_LEAK_KEYS = FORBIDDEN_KEYS | {"allowed", "board_line", "original", "verdict", "avoids", "sound"}


def test_a_practice_session_works_over_http_and_leaks_nothing_before_the_answer(store):
    conn = store.conn
    import random

    for t in A.TYPES:  # the starting tests are done
        finish(conn, A.start_baseline(conn, t, rng=random.Random(3), now=T0)["assessment_id"])
    for _ in range(4):
        store.position("M1", pool="PRACTICE")
    heldout = heldout_fens(conn)
    home = client.get("/coach/home").json()["types"][0]["practice"]
    assert home["unlocked"] is True and home["session"] is None and home["positions"]["unseen"] >= 5

    started = client.post("/coach/practice/sessions", json={"mistake_type": "M1"}).json()
    sid = started["session_id"]
    assert started["resumed"] is False
    assert client.post("/coach/practice/sessions", json={"mistake_type": "M1"}).json()["resumed"] is True
    bodies = []
    view = client.get(f"/coach/practice/sessions/{sid}").json()
    while view["current"]:
        cur = view["current"]
        bodies.append(view)
        assert not PRACTICE_LEAK_KEYS & set(keys(view)), PRACTICE_LEAK_KEYS & set(keys(view))  # before the first answer
        assert cur["stage"] == "recognition" and cur["feedback"] is None and cur["hints"] == []
        r = client.post(f"/coach/practice/sessions/{sid}/recognition", json={"ord": cur["ord"], "tap": "h7"})
        assert r.status_code == 200 and not PRACTICE_LEAK_KEYS & set(keys(r.json()))
        r = client.post(f"/coach/practice/sessions/{sid}/move", json={"ord": cur["ord"], "move": "h7h1"})
        fb = r.json()["current"]["feedback"]
        assert fb["sound"] is True and fb["target_squares"] == ["h7"]
        bodies.append(r.json())
        view = client.post(f"/coach/practice/sessions/{sid}/next", json={"ord": cur["ord"]}).json()
    assert view["status"] == "completed"
    summary = client.get(f"/coach/practice/sessions/{sid}/summary").json()
    bodies.append(summary)
    assert summary["assisted"] is True and summary["first_attempt_correct"] == 5
    text = json.dumps(bodies)
    assert not [f for f in heldout if f'"{f}"' in text]  # a held-out board never reaches a practice response


def test_practice_errors_use_stable_codes(store):
    conn = store.conn
    r = client.post("/coach/practice/sessions", json={"mistake_type": "M1"})
    assert r.status_code == 409 and r.json()["error"] == "baseline_needed"
    assert client.get("/coach/practice/sessions/999").status_code == 404
    import random

    finish(conn, A.start_baseline(conn, "M1", rng=random.Random(3), now=T0)["assessment_id"])
    sid = client.post("/coach/practice/sessions", json={"mistake_type": "M1"}).json()["session_id"]
    cur = client.get(f"/coach/practice/sessions/{sid}").json()["current"]
    r = client.post(f"/coach/practice/sessions/{sid}/move", json={"ord": cur["ord"], "move": "h7h1"})
    assert r.status_code == 409 and r.json()["error"] == "wrong_step"
    r = client.post(f"/coach/practice/sessions/{sid}/recognition", json={"ord": cur["ord"], "tap": "e7"})
    assert r.status_code == 400 and r.json()["error"] == "tap_a_piece"
    r = client.get(f"/coach/practice/sessions/{sid}/summary")
    assert r.status_code == 409 and r.json()["error"] == "not_finished"
