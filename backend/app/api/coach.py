"""PRD v2 routes (Step 2: home and the baseline assessment). Thin: every rule lives in `app/learner/assessment.py`, which
the MCP server will call too (PRD §11).

These are the only routes that read the position store, and only `/coach/assessments/...` can return a held-out board
(tested in `tests/test_coach_api.py`).

The random-guess move rate needs every legal move of a position judged by the evidence engine (about a minute a position),
so it is computed in the background from the moment a baseline starts, while the player answers. The results page shows
the scores at once and the random-guess move rate when it is ready.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.schema import connect
from app.engine.evidence import open_evidence
from app.learner import assessment as A
from app.learner import practice as P
from app.learner import progress as G
from app.learner import realgame_rates as RG

log = logging.getLogger(__name__)

DB_PATH: Path | str | None = None  # None: data/coach.sqlite3. Tests point this at a temporary store.
open_analyser = open_evidence  # replaced by a scripted analyser in tests
CHANCE_WORKERS = 5  # one engine process per position of an assessment

AssessmentError = A.AssessmentError  # for `main.py`'s error handler: no other API module imports the service
router = APIRouter(prefix="/coach")
_executor = ThreadPoolExecutor(max_workers=CHANCE_WORKERS, thread_name_prefix="move-chance")
_running: set[int] = set()
_lock = threading.Lock()

STATUS = {
    "not_found": 404,
    "not_due_yet": 403,
    "test_waiting": 409,
    "unknown_mistake_type": 400,
    "tap_a_piece": 400,
    "not_a_baseline": 400,
    "already_set_aside": 409,
    "reason_needed": 400,
    "illegal_move": 400,
    "baseline_done": 409,
    "baseline_needed": 409,
    "not_enough_practice_positions": 409,
    "session_completed": 409,
    "wrong_step": 409,
    "pool_too_small": 409,
    "not_current_position": 409,
    "assessment_submitted": 409,
    "not_finished": 409,
    "not_submitted": 403,
    "engine_config_changed": 503,
}


def db() -> Iterator:
    conn = connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _chance_one(position_id: int) -> None:
    conn = None
    try:
        conn = connect(DB_PATH)
        with open_analyser(conn) as analyser:
            A.compute_move_chance(conn, position_id, analyser)
    except Exception:  # the results page keeps saying "still calculating" and retries
        log.exception("random-guess move rate failed for position %s", position_id)
    finally:
        if conn is not None:
            conn.close()
        with _lock:
            _running.discard(position_id)


def start_chance_job(position_ids: list[int]) -> None:
    """Compute missing random-guess move rates in the background; a position already being computed is skipped."""
    with _lock:
        todo = [p for p in position_ids if p not in _running]
        _running.update(todo)
    for pid in todo:
        _executor.submit(_chance_one, pid)


Conn = Annotated[sqlite3.Connection, Depends(db)]


class StartBaseline(BaseModel):
    mistake_type: str


class ItemIn(BaseModel):
    ord: int
    recognition: str  # a square with a piece on it, or "none" for "No immediate threat"
    move: str  # UCI


class StartSession(BaseModel):
    mistake_type: str


class RecognitionIn(BaseModel):
    ord: int
    tap: str  # a square with a piece on the asked side, or "none"


class MoveIn(BaseModel):
    ord: int
    move: str  # UCI


class OrdIn(BaseModel):
    ord: int


@router.get("/home")
def home(conn: Conn):
    out = A.home(conn)
    for t in out["types"]:
        t["practice"] = P.home_status(conn, t["mistake_type"])
    return out


@router.post("/assessments/baseline")
def start_baseline(body: StartBaseline, conn: Conn):
    started = A.start_baseline(conn, body.mistake_type)
    start_chance_job(A.missing_move_chances(conn, started["assessment_id"]))
    return started


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: int, conn: Conn):
    out = A.get_assessment(conn, assessment_id)
    if out.get("available") and out["assessment_kind"] == "DELAYED":  # the delayed test just opened: work out its guessing rates
        start_chance_job(A.missing_move_chances(conn, assessment_id))
    return out


@router.post("/assessments/{assessment_id}/items")
def submit_item(assessment_id: int, body: ItemIn, conn: Conn):
    with open_analyser(conn) as analyser:
        return A.submit_item(conn, assessment_id, body.ord, body.recognition, body.move, analyser)


@router.post("/assessments/{assessment_id}/submit")
def submit(assessment_id: int, conn: Conn):
    A.submit(conn, assessment_id)
    return results(assessment_id, conn)


@router.get("/assessments/{assessment_id}/results")
def results(assessment_id: int, conn: Conn):
    out = A.results(conn, assessment_id)
    if out["chance_pending"]:
        start_chance_job(A.missing_move_chances(conn, assessment_id))
    return out


# --- Replay My Mistakes (PRD v2 §6): assisted practice, practice-pool positions only ----------------------------------


@router.post("/practice/sessions")
def start_session(body: StartSession, conn: Conn):
    return P.start_session(conn, body.mistake_type)


@router.get("/practice/sessions/{session_id}")
def get_session(session_id: int, conn: Conn):
    return P.get_session(conn, session_id)


@router.post("/practice/sessions/{session_id}/recognition")
def practice_recognition(session_id: int, body: RecognitionIn, conn: Conn):
    return P.submit_recognition(conn, session_id, body.ord, body.tap)


@router.post("/practice/sessions/{session_id}/move")
def practice_move(session_id: int, body: MoveIn, conn: Conn):
    with open_analyser(conn) as analyser:
        return P.submit_move(conn, session_id, body.ord, body.move, analyser)


@router.post("/practice/sessions/{session_id}/hint")
def practice_hint(session_id: int, body: OrdIn, conn: Conn):
    return P.hint(conn, session_id, body.ord)


@router.post("/practice/sessions/{session_id}/retry")
def practice_retry(session_id: int, body: OrdIn, conn: Conn):
    return P.retry(conn, session_id, body.ord)


@router.post("/practice/sessions/{session_id}/next")
def practice_next(session_id: int, body: OrdIn, conn: Conn):
    return P.next_position(conn, session_id, body.ord)


@router.get("/practice/sessions/{session_id}/summary")
def practice_summary(session_id: int, conn: Conn):
    return P.summary(conn, session_id)


@router.get("/progress")
def progress(conn: Conn):
    return G.progress(conn)


@router.get("/progress/realgame")
def progress_realgame(conn: Conn):
    """Real-game rates with floors (PRD v2 §8): reads stored per-game results only, never starts an engine."""
    return RG.rates(conn)
