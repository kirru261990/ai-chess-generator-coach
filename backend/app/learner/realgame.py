"""Real-game windows (PRD v2 §8). Step 2 builds the frozen baseline window; the rates and the post window come in Step 4.

When the first practice session for a mistake type starts, the last WINDOW_GAMES games per time control played before that
moment are frozen as the baseline window. The database refuses any later edit or delete (`app/db/schema.py`), and freezing
again returns the rows already frozen. Both pools count: the window measures real play, not which positions are tested.
This is not the 7 Oct window (ADR 0002), which stays as history (ADR 0006 decision 4).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from app.db.schema import transaction
from app.learner.assessment import TYPES, AssessmentError, user

WINDOW_GAMES = 30
# M3 (missed threat, ADR 0011) has a real-game window but no practice or assessment yet, so it is frozen on demand
# (`realgame_rates freeze`) before any M3 training, not by a practice session.
WINDOW_TYPES = (*TYPES, "M3")


def frozen_windows(conn: sqlite3.Connection, mistake_type: str) -> list[dict]:
    rows = conn.execute(
        "SELECT time_control, game_ids_json, frozen_at FROM baseline_window WHERE user = ? AND mistake_type = ?"
        " ORDER BY time_control",
        (user(), mistake_type),
    ).fetchall()
    return [{"time_control": r["time_control"], "game_ids": json.loads(r["game_ids_json"]), "frozen_at": r["frozen_at"]}
            for r in rows]


def freeze_in_transaction(conn: sqlite3.Connection, mistake_type: str, *, now: datetime) -> None:
    """Freeze the windows for a type if none exist. The caller holds the transaction (so starting a practice session and
    freezing its window succeed or fail together, review on PR 72)."""
    if frozen_windows(conn, mistake_type):
        return
    tcs = [r[0] for r in conn.execute("SELECT DISTINCT time_control FROM game ORDER BY time_control")]
    for tc in tcs:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM game WHERE time_control = ? AND played_at < ? ORDER BY played_at DESC, id LIMIT ?",
            (tc, int(now.timestamp()), WINDOW_GAMES),
        )]
        conn.execute(
            "INSERT INTO baseline_window (user, mistake_type, time_control, game_ids_json, frozen_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (user(), mistake_type, tc, json.dumps(ids), now.isoformat(timespec="seconds")),
        )


def freeze_baseline_window(conn: sqlite3.Connection, mistake_type: str, *, now: datetime | None = None) -> list[dict]:
    """Freeze the last WINDOW_GAMES games per time control before `now` for this type, once. Returns the frozen windows."""
    if mistake_type not in WINDOW_TYPES:
        raise AssessmentError("unknown_mistake_type", f"mistake type must be one of {', '.join(WINDOW_TYPES)}")
    now = now or datetime.now(UTC)
    with transaction(conn):
        freeze_in_transaction(conn, mistake_type, now=now)
    return frozen_windows(conn, mistake_type)
