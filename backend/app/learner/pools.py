"""Pools (PRD v2 §5.1, ADR 0006 decision 7): each game is PRACTICE or HELDOUT for good, decided at import.

HELDOUT when sha256(Chess.com game id) mod 100 < HELDOUT_PERCENT. The hash depends on the game alone, so a game's pool never
depends on which other games exist and never changes as games arrive; the split is about 60/40 in each time control and the
real split is reported (`pool_counts`). The database refuses any later change of pool (`app/db/schema.py`).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from app.engine.batch import game_id

HELDOUT_PERCENT = 40
SOURCE = "chesscom"


def pool_for(platform_id: str) -> str:
    bucket = int.from_bytes(hashlib.sha256(platform_id.encode()).digest()[:8], "big") % 100
    return "HELDOUT" if bucket < HELDOUT_PERCENT else "PRACTICE"


def row_id(platform_id: str) -> str:
    return f"{SOURCE}:{platform_id}"


def import_games(conn: sqlite3.Connection, games_path: Path, time_controls) -> int:
    """Add synced games of the given time controls to `game` with their pool. Already imported games are left alone.

    Returns the number of games added.
    """
    added = 0
    with games_path.open() as f:
        for line in f:
            if not line.strip():
                continue
            g = json.loads(line)
            if g["time_control"] not in time_controls:
                continue
            pid = game_id(g["source_id"])
            cur = conn.execute(
                "INSERT OR IGNORE INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row_id(pid), SOURCE, pid, g["user_color"], g["time_control"], g["end_time"], pool_for(pid), g["pgn"]),
            )
            added += cur.rowcount
            if not cur.rowcount:  # already imported: fill a colour an upgraded store could not read from the PGN
                conn.execute(
                    "UPDATE game SET user_color = ? WHERE id = ? AND user_color IS NULL", (g["user_color"], row_id(pid))
                )
    return added


def pool_counts(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in conn.execute("SELECT time_control, pool, COUNT(*) AS n FROM game GROUP BY time_control, pool"):
        out.setdefault(row["time_control"], {})[row["pool"]] = row["n"]
    return out
