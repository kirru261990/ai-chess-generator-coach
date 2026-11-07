"""Drill cycles (ADR 0018): the same fixed set of drills, solved again and again, each pass faster (the Woodpecker idea).

A *set* is a frozen list of drills copied out of the drill bank (ADR 0017), so rebuilding the bank never changes it. A *cycle* is
one pass over the set, in a new order each time after the first. Per cycle we keep matched / answered, the time, and compare
with the cycle before. No file of this module touches `data/coach.sqlite3` (ADR 0017 decision 8): the ledger is
`data/drills/cycles.sqlite3`.

- **Correct means "matched a verified move".** M1: one of the drill's engine-verified safe alternatives. M2: the engine's free
  capture. Any other legal move is "not one of the checked moves", never "wrong": the engine did not rule on it (rule 5).
- **Practice, so always assisted** (ADR 0005): the answer is shown at once and you may look at the line. There is no hint button
  in cycles, and nothing is shown before you move (the leak test in `tests/test_drillcycle.py`).
- **Rates with denominators** (rule 3): matched out of answered, and the share a random legal move would match.
- **Time is measured by the server**: from the first time a position is shown to the answer, capped at ELAPSED_CAP_MS so a
  break does not count as thinking.
Imports no LLM code. Drill text is data only.
"""

from __future__ import annotations

import json
import random
import sqlite3
import statistics
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import chess

from app.learner import drillbank, drilltiming

VERSION = "1"
SET_SIZE = 50
MIN_SET_SIZE = 10
ELAPSED_CAP_MS = 600_000
TYPES = ("M1", "M2")  # M3 is experimental (ADR 0017 decision 5)

SCHEMA = """
CREATE TABLE IF NOT EXISTS cycle_set (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  bank_version TEXT NOT NULL,
  cycle_version TEXT NOT NULL,
  drills TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cycle (
  id INTEGER PRIMARY KEY,
  set_id INTEGER NOT NULL REFERENCES cycle_set(id),
  number INTEGER NOT NULL,
  order_json TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  UNIQUE (set_id, number)
);
CREATE TABLE IF NOT EXISTS attempt (
  cycle_id INTEGER NOT NULL REFERENCES cycle(id),
  drill_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  shown_at TEXT NOT NULL,
  answered_at TEXT,
  move_uci TEXT,
  matched INTEGER,
  elapsed_ms INTEGER,
  assisted INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (cycle_id, drill_id)
);
"""


class CycleError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def ledger_path() -> Path:
    return drillbank.bank_dir() / "cycles.sqlite3"


def connect() -> sqlite3.Connection:
    ledger_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ledger_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


# --- the set ---------------------------------------------------------------------------------------------------------------


def read_bank() -> list[dict]:
    p = drillbank.bank_path()
    if not p.exists():
        raise CycleError("no_drill_bank", "The drill library has not been built on this computer yet, so there is nothing to practise.")
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def accepted_moves(drill: dict) -> list[str]:
    """The moves that count as a match, as UCI. Only moves the engine verified (see the module note)."""
    e = drill["evidence"]
    if drill["type"] == "M1":
        return [a["uci"] for a in drill.get("alternatives", [])]
    caught = [c["uci"] for c in e.get("free_captures", [])]
    first = e["refutation_line"]["uci"][0]
    return caught if first in caught else [first, *caught]


def build_set(drills: list[dict], timing: dict[str, str], size: int = SET_SIZE) -> list[dict]:
    """Up to `size` drills, half of each type, easiest (lowest average rating) first, one per game, no experimental drill, no
    drill without a verified answer, no missed-free-piece drill whose timing is `unclear`. Ties break by drill id."""
    def usable(d: dict) -> bool:
        return (d["type"] in TYPES and not d.get("experimental") and accepted_moves(d)
                and not (d["type"] == "M2" and timing.get(d["id"], "unclear") == "unclear"))

    def key(d: dict):
        return (d["avg_rating"] is None, d["avg_rating"] or 0, d["id"])

    games: set[str] = set()
    picked: dict[str, list[dict]] = {t: [] for t in TYPES}
    quota = {"M1": (size + 1) // 2, "M2": size // 2}
    for d in sorted((d for d in drills if usable(d)), key=key):
        if len(picked[d["type"]]) < quota[d["type"]] and d["game_id"] not in games:
            games.add(d["game_id"])
            picked[d["type"]].append(d)
    # the other type tops up a short one, so a thin bank still gives a full set
    for t, other in (("M1", "M2"), ("M2", "M1")):
        short = quota[t] - len(picked[t])
        if short > 0:
            for d in sorted((d for d in drills if usable(d) and d["type"] == other), key=key):
                if short and d["game_id"] not in games and d not in picked[other]:
                    games.add(d["game_id"])
                    picked[other].append(d)
                    short -= 1
    chosen = sorted(picked["M1"] + picked["M2"], key=key)
    return [{**d, "timing": timing.get(d["id"])} for d in chosen[:size]]


def _snapshot(d: dict) -> dict:
    keep = ("id", "type", "fen", "side", "played", "played_san", "game_id", "avg_rating", "timing", "versions")
    e = d["evidence"]
    return {**{k: d.get(k) for k in keep}, "alternatives": d.get("alternatives", []), "accepted": accepted_moves(d),
            "evidence": {k: e.get(k) for k in ("lost_piece_square_after", "target_squares", "refutation_line")}}


def current_set(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM cycle_set ORDER BY id DESC LIMIT 1").fetchone()


def _set_drills(row: sqlite3.Row) -> dict[str, dict]:
    return {d["id"]: d for d in json.loads(row["drills"])}


def _lock(conn: sqlite3.Connection) -> None:
    """Start a write transaction before the existence check, so two requests cannot both decide something is missing."""
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")


def ensure_set(conn: sqlite3.Connection) -> sqlite3.Row:
    row = current_set(conn)
    if row is not None:
        return row
    drills = build_set(read_bank(), drilltiming.read_timing())
    if len(drills) < MIN_SET_SIZE:
        raise CycleError("drill_bank_too_small", f"Only {len(drills)} drills are usable; a cycle needs at least {MIN_SET_SIZE}.")
    _lock(conn)
    try:
        if current_set(conn) is None:  # another request may have made it while the bank was read
            conn.execute("INSERT INTO cycle_set (created_at, bank_version, cycle_version, drills) VALUES (?, ?, ?, ?)",
                         (_now(), drillbank.BANK_VERSION, VERSION, json.dumps([_snapshot(d) for d in drills])))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return current_set(conn)


# --- cycles -----------------------------------------------------------------------------------------------------------------


def _order(set_row: sqlite3.Row, number: int) -> list[str]:
    ids = [d["id"] for d in json.loads(set_row["drills"])]  # stored easiest first
    if number > 1:
        random.Random(f"cycle-{set_row['id']}-{number}").shuffle(ids)
    return ids


def open_cycle(conn: sqlite3.Connection) -> sqlite3.Row:
    """The cycle in progress, or the next one (a finished cycle is never reopened)."""
    s = ensure_set(conn)
    _lock(conn)
    try:
        row = conn.execute("SELECT * FROM cycle WHERE set_id = ? AND finished_at IS NULL ORDER BY number DESC LIMIT 1", (s["id"],)).fetchone()
        if row is None:
            last = conn.execute("SELECT MAX(number) FROM cycle WHERE set_id = ?", (s["id"],)).fetchone()[0] or 0
            conn.execute("INSERT INTO cycle (set_id, number, order_json, started_at) VALUES (?, ?, ?, ?)",
                         (s["id"], last + 1, json.dumps(_order(s, last + 1)), _now()))
            row = conn.execute("SELECT * FROM cycle WHERE set_id = ? AND number = ?", (s["id"], last + 1)).fetchone()
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return row


def _next_drill(conn: sqlite3.Connection, cyc: sqlite3.Row) -> tuple[int, str] | None:
    done = {r[0] for r in conn.execute("SELECT drill_id FROM attempt WHERE cycle_id = ? AND answered_at IS NOT NULL", (cyc["id"],))}
    for pos, did in enumerate(json.loads(cyc["order_json"])):
        if did not in done:
            return pos, did
    return None


SIDE = {"white": "White", "black": "Black"}
M2_ASK = {
    "right_away": "Find the capture that wins material right away.",
    "next_move": "Find the capture that wins material by your next move.",
    "within_3_moves": "Find the capture that wins material within your next 3 moves.",
}


def question(d: dict) -> str:
    if d["type"] == "M1":
        return "Find a move that does not leave one of your pieces to be won."
    return M2_ASK.get(d.get("timing") or "", "Find the capture that wins material.")


def current(conn: sqlite3.Connection) -> dict:
    """What to show now. Before the answer: the board, who moves, the legal moves, the question, and nothing else."""
    cyc = open_cycle(conn)
    nxt = _next_drill(conn, cyc)
    if nxt is None:
        return finish(conn, cyc)
    pos, did = nxt
    d = _set_drills(current_set(conn))[did]
    conn.execute("INSERT OR IGNORE INTO attempt (cycle_id, drill_id, position, shown_at) VALUES (?, ?, ?, ?)", (cyc["id"], did, pos, _now()))
    conn.commit()
    board = chess.Board(d["fen"])
    return {"done": False, "cycle": cyc["number"], "position": pos + 1, "total": len(json.loads(cyc["order_json"])), "drill_id": did,
            "fen": d["fen"], "side": d["side"], "question": question(d), "legal_moves": sorted(m.uci() for m in board.legal_moves)}


def finish(conn: sqlite3.Connection, cyc: sqlite3.Row) -> dict:
    with conn:
        conn.execute("UPDATE cycle SET finished_at = COALESCE(finished_at, ?) WHERE id = ?", (_now(), cyc["id"]))
    return {"done": True, "cycle": cyc["number"], "summary": summary(conn)}


def _san(fen: str, uci: str) -> str:
    return chess.Board(fen).san(chess.Move.from_uci(uci))


def answer(conn: sqlite3.Connection, drill_id: str, move_uci: str) -> dict:
    cyc = open_cycle(conn)
    row = conn.execute("SELECT * FROM attempt WHERE cycle_id = ? AND drill_id = ?", (cyc["id"], drill_id)).fetchone()
    if row is None:
        raise CycleError("not_current_position", "That position is not the one on screen.")
    if row["answered_at"] is not None:
        raise CycleError("already_answered", "That position was already answered in this cycle.")
    d = _set_drills(current_set(conn))[drill_id]
    board = chess.Board(d["fen"])
    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError:
        move = None
    if move is None or move not in board.legal_moves:
        raise CycleError("illegal_move", "That move is not legal in this position.")
    shown = datetime.fromisoformat(row["shown_at"])
    elapsed = min(ELAPSED_CAP_MS, max(0, int((datetime.now(UTC) - shown).total_seconds() * 1000)))
    matched = move_uci in d["accepted"]
    with conn:  # only the first answer is accepted: the guard and the row count settle two tabs answering at once
        taken = conn.execute("UPDATE attempt SET answered_at = ?, move_uci = ?, matched = ?, elapsed_ms = ?"
                             " WHERE cycle_id = ? AND drill_id = ? AND answered_at IS NULL",
                             (_now(), move_uci, int(matched), elapsed, cyc["id"], drill_id)).rowcount
    if taken == 0:
        raise CycleError("already_answered", "That position was already answered in this cycle.")
    return feedback(d, board, move, matched, elapsed)


def feedback(d: dict, board: chess.Board, move: chess.Move, matched: bool, elapsed_ms: int) -> dict:
    ref = d["evidence"]["refutation_line"]
    out = {"matched": matched, "your_move": board.san(move), "checked_moves": [_san(d["fen"], u) for u in d["accepted"]],
           "checked_uci": d["accepted"],
           "elapsed_ms": elapsed_ms, "assisted": True}
    if d["type"] == "M1":
        out["in_the_game"] = d["played_san"]
        out["line"] = ref["san"]
        out["note"] = (f"In the game {d['played_san']} was played and the piece on {d['evidence']['lost_piece_square_after']} could then be won:"
                       f" {' '.join(ref['san'])}.")
    else:
        out["in_the_game"] = d["played_san"]
        out["line"] = ref["san"]
        out["note"] = f"In the game {d['played_san']} was played instead. The checked line is {' '.join(ref['san'])}."
    if not matched:
        out["not_checked"] = "This move is not one of the engine-checked moves. That does not mean it is bad: the engine did not rule on it."
    return out


# --- progress ---------------------------------------------------------------------------------------------------------------


def chance_rate(drills: dict[str, dict], ids: list[str]) -> float | None:
    """Share of the answered positions a random legal move would have matched, averaged over those positions."""
    shares = []
    for i in ids:
        d = drills[i]
        legal = {m.uci() for m in chess.Board(d["fen"]).legal_moves}
        if legal:
            shares.append(len(legal & set(d["accepted"])) / len(legal))
    return round(sum(shares) / len(shares), 3) if shares else None


def summary(conn: sqlite3.Connection) -> dict:
    s = current_set(conn)
    if s is None:
        return {"has_set": False, "cycles": []}
    drills = _set_drills(s)
    cycles = []
    for c in conn.execute("SELECT * FROM cycle WHERE set_id = ? ORDER BY number", (s["id"],)):
        rows = conn.execute("SELECT * FROM attempt WHERE cycle_id = ? AND answered_at IS NOT NULL", (c["id"],)).fetchall()
        times = [r["elapsed_ms"] for r in rows]
        cycles.append({
            "number": c["number"], "finished": c["finished_at"] is not None, "answered": len(rows), "total": len(drills),
            "matched": sum(r["matched"] for r in rows), "total_ms": sum(times),
            "median_ms": int(statistics.median(times)) if times else None,
            "chance": chance_rate(drills, [r["drill_id"] for r in rows]),
        })
    for prev, cur in pairwise(cycles):
        if prev["finished"] and cur["answered"]:
            cur["vs_previous"] = {"total_ms": cur["total_ms"] - prev["total_ms"], "matched": cur["matched"] - prev["matched"],
                                  "same_size": cur["answered"] == prev["answered"]}
    return {"has_set": True, "set_id": s["id"], "size": len(drills), "versions": {"cycle": s["cycle_version"], "bank": s["bank_version"]},
            "cycles": cycles}
