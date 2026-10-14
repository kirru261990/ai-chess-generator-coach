"""Boards the owner has already seen outside an assessment (ADR 0006 decision 5; PRD §5.3).

One move can be stored as several position rows (an M1 row and an M2 row for the same game and ply). Seeing one of them
means seeing the board, so "seen" is a property of the board: marking a row marks all its sibling rows, and a selection of
unseen positions skips any board with a seen row. `propagate` repairs rows marked before this rule existed (review on PR 64).
"""

from __future__ import annotations

import sqlite3

# For a query over `position`: true when no row of the same game and ply is marked seen.
UNSEEN_BOARD = (
    "NOT EXISTS (SELECT 1 FROM position s WHERE s.game_id = position.game_id AND s.ply = position.ply"
    " AND s.excluded_reason IS NOT NULL)"
)


def mark_seen(conn: sqlite3.Connection, position_id: int, reason: str) -> None:
    """Mark a position and every other row for the same board. Rows already marked keep their reason."""
    conn.execute(
        "UPDATE position SET excluded_reason = ? WHERE excluded_reason IS NULL AND (id = ? OR (game_id, ply) IN"
        " (SELECT game_id, ply FROM position WHERE id = ? AND game_id IS NOT NULL))",
        (reason, position_id, position_id),
    )


def propagate(conn: sqlite3.Connection) -> int:
    """Give every unmarked sibling of a marked row that row's reason. Returns the number of rows marked."""
    cur = conn.execute(
        "UPDATE position SET excluded_reason = (SELECT m.excluded_reason FROM position m WHERE m.game_id = position.game_id"
        " AND m.ply = position.ply AND m.excluded_reason IS NOT NULL ORDER BY m.id LIMIT 1)"
        " WHERE excluded_reason IS NULL AND game_id IS NOT NULL AND NOT " + UNSEEN_BOARD
    )
    return cur.rowcount
