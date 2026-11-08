"""Rounds of first-slip drills (ADR 0020): ten positions, five from the player's own games and five fresh ones from public games.

Practice, so always assisted (ADR 0005). Imports no LLM code. Drill text is data only.
"""

from __future__ import annotations

ROUND_OWN = 5
ROUND_FRESH = 5
ROUND_SIZE = ROUND_OWN + ROUND_FRESH


class RoundError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _easiest_first(d: dict):
    return (d["avg_rating"] is None, d["avg_rating"] or 0, d["id"])


def position_key(d: dict) -> str:
    """The same position and move across finder versions (drill ids differ by version)."""
    return f"{d['fen']}|{d['played']}"


def build_round(drills: list[dict], exclude: set[str] | frozenset[str] = frozenset()) -> list[dict]:
    """Five own and five fresh drills, one per game, easiest (lowest average rating) first within each source. A short source is
    topped up from the other; drills in `exclude` (drill ids or position keys used in earlier rounds) are skipped. Fewer than ten usable drills is an error."""
    pool = sorted((d for d in drills if d["type"] == "S1" and d["accepted"] and d["id"] not in exclude and position_key(d) not in exclude), key=_easiest_first)
    games: set[str] = set()
    picked: dict[str, list[dict]] = {"own": [], "lichess": []}
    quota = {"own": ROUND_OWN, "lichess": ROUND_FRESH}

    def take(source: str, limit: int) -> None:
        for d in pool:
            if len(picked[source]) >= limit:
                return
            if d["source"] == source and d["game_id"] not in games:
                games.add(d["game_id"])
                picked[source].append(d)

    for source, n in quota.items():
        take(source, n)
    for source, other in (("own", "lichess"), ("lichess", "own")):
        short = quota[source] - len(picked[source])
        if short > 0:
            take(other, len(picked[other]) + short)
    chosen = picked["own"] + picked["lichess"]
    if len(chosen) < ROUND_SIZE:
        raise RoundError("round_too_small", f"Only {len(chosen)} first-slip drills are usable; a round needs {ROUND_SIZE}.")
    return chosen


# --- a round in progress ---------------------------------------------------------------------------------------------------
# The ledger is its own file (`data/drills/slip_rounds.sqlite3`), apart from the cycle ledger and `data/coach.sqlite3`, so the
# frozen cycle set and the owner's cycle-1 result stay as they are (ADR 0020 decision 4, reversal).

import json
import sqlite3
import statistics
from datetime import UTC, datetime
from pathlib import Path

import chess

from app.learner import drillbank, slipfinder
from app.learner.drillcycle import ELAPSED_CAP_MS

VERSION = "1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS slip_round (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  round_version TEXT NOT NULL,
  drills TEXT NOT NULL,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS slip_attempt (
  round_id INTEGER NOT NULL REFERENCES slip_round(id),
  drill_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  shown_at TEXT NOT NULL,
  answered_at TEXT,
  move_uci TEXT,
  matched INTEGER,
  elapsed_ms INTEGER,
  assisted INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (round_id, drill_id)
);
"""


def slips_path() -> Path:
    return drillbank.bank_dir() / "slips_v1.jsonl"


def ledger_path() -> Path:
    return drillbank.bank_dir() / "slip_rounds.sqlite3"


def connect() -> sqlite3.Connection:
    ledger_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ledger_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def read_slips() -> list[dict]:
    p = slips_path()
    if not p.exists():
        raise RoundError("no_slip_drills", "No first-slip drills have been built on this computer yet, so there is nothing to practise.")
    drills = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    # only drills from the current finder and record layout are served; older ones stay in the file as history
    return [d for d in drills if d.get("versions", {}).get("slip_finder") == slipfinder.VERSION
            and d["versions"].get("bank") == slipfinder.BANK_VERSION]


def _snapshot(d: dict) -> dict:
    keep = ("id", "type", "source", "fen", "side", "played", "played_san", "game_id", "avg_rating", "accepted", "versions")
    return {**{k: d.get(k) for k in keep}, "loss_cp": d["evidence"]["loss_cp"]}


def _open_round(conn: sqlite3.Connection, create: bool = True) -> sqlite3.Row:
    """The round in progress, or (only when `create`) a new one built from drills no earlier round used."""
    row = conn.execute("SELECT * FROM slip_round WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    if row is not None:
        return row
    if not create:
        raise RoundError("not_current_position", "No round is open, so there is no position to answer.")
    slips = read_slips()  # a file read; the choice below is made under the lock, so a round another request just finished is seen
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")  # two requests must not both start a round
    try:
        row = conn.execute("SELECT * FROM slip_round WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            used = {k for r in conn.execute("SELECT drills FROM slip_round") for d in json.loads(r["drills"]) for k in (d["id"], position_key(d))}
            chosen = build_round(slips, exclude=used)
            conn.execute("INSERT INTO slip_round (created_at, round_version, drills) VALUES (?, ?, ?)",
                         (_now(), VERSION, json.dumps([_snapshot(d) for d in chosen])))
            row = conn.execute("SELECT * FROM slip_round WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return row


def _drills(row: sqlite3.Row) -> list[dict]:
    return json.loads(row["drills"])


def _number(conn: sqlite3.Connection, row: sqlite3.Row) -> int:
    return conn.execute("SELECT COUNT(*) FROM slip_round WHERE id <= ?", (row["id"],)).fetchone()[0]


def current(conn: sqlite3.Connection) -> dict:
    """What to show now. Before the answer: the board, who moves, the legal moves, the question, and nothing else."""
    rnd = _open_round(conn)
    drills = _drills(rnd)
    done = {r[0] for r in conn.execute("SELECT drill_id FROM slip_attempt WHERE round_id = ? AND answered_at IS NOT NULL", (rnd["id"],))}
    for pos, d in enumerate(drills):
        if d["id"] not in done:
            conn.execute("INSERT OR IGNORE INTO slip_attempt (round_id, drill_id, position, shown_at) VALUES (?, ?, ?, ?)",
                         (rnd["id"], d["id"], pos, _now()))
            conn.commit()
            side = "White" if d["side"] == "white" else "Black"
            return {"done": False, "round": _number(conn, rnd), "position": pos + 1, "total": len(drills), "drill_id": d["id"],
                    "fen": d["fen"], "side": d["side"], "question": f"Find the best move for {side}.",
                    "legal_moves": sorted(m.uci() for m in chess.Board(d["fen"]).legal_moves)}
    with conn:
        conn.execute("UPDATE slip_round SET finished_at = COALESCE(finished_at, ?) WHERE id = ?", (_now(), rnd["id"]))
    return {"done": True, "round": _number(conn, rnd), "summary": summary(conn, rnd)}


def answer(conn: sqlite3.Connection, drill_id: str, move_uci: str) -> dict:
    rnd = _open_round(conn, create=False)  # answering never starts a round
    row = conn.execute("SELECT * FROM slip_attempt WHERE round_id = ? AND drill_id = ?", (rnd["id"], drill_id)).fetchone()
    if row is None:
        raise RoundError("not_current_position", "That position is not the one on screen.")
    if row["answered_at"] is not None:
        raise RoundError("already_answered", "That position was already answered in this round.")
    d = next(x for x in _drills(rnd) if x["id"] == drill_id)
    board = chess.Board(d["fen"])
    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError:
        move = None
    if move is None or move not in board.legal_moves:
        raise RoundError("illegal_move", "That move is not legal in this position.")
    elapsed = min(ELAPSED_CAP_MS, max(0, int((datetime.now(UTC) - datetime.fromisoformat(row["shown_at"])).total_seconds() * 1000)))
    matched = move_uci in d["accepted"]
    with conn:  # only the first answer is accepted
        taken = conn.execute("UPDATE slip_attempt SET answered_at = ?, move_uci = ?, matched = ?, elapsed_ms = ?"
                             " WHERE round_id = ? AND drill_id = ? AND answered_at IS NULL",
                             (_now(), move_uci, int(matched), elapsed, rnd["id"], drill_id)).rowcount
    if taken == 0:
        raise RoundError("already_answered", "That position was already answered in this round.")
    out = {"matched": matched, "your_move": board.san(move), "checked_uci": d["accepted"],
           "checked_moves": [board.san(chess.Move.from_uci(u)) for u in d["accepted"]], "in_the_game": d["played_san"],
           "note": f"In the game {d['played_san']} was played; by the engine's count it gave up about {d['loss_cp'] / 100:.1f} pawns.",
           "elapsed_ms": elapsed, "assisted": True}
    if not matched:
        out["not_checked"] = "This move is not one of the engine-checked moves. That does not mean it is bad: the engine did not rule on it."
    return out


def summary(conn: sqlite3.Connection, rnd: sqlite3.Row) -> dict:
    rows = conn.execute("SELECT * FROM slip_attempt WHERE round_id = ? AND answered_at IS NOT NULL", (rnd["id"],)).fetchall()
    times = [r["elapsed_ms"] for r in rows]
    return {"answered": len(rows), "total": len(_drills(rnd)), "matched": sum(r["matched"] for r in rows),
            "total_ms": sum(times), "median_ms": int(statistics.median(times)) if times else None,
            "versions": {"round": rnd["round_version"]}}


def overview(conn: sqlite3.Connection) -> list[dict]:
    """Every round so far with its summary, so a finished round can be read again after the next one has started."""
    return [{"round": i, "finished": r["finished_at"] is not None, "summary": summary(conn, r)}
            for i, r in enumerate(conn.execute("SELECT * FROM slip_round ORDER BY id"), 1)]
