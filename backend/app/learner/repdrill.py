"""Opening line drills (ADR 0022): play a repertoire line from move 1; a miss brings the line back sooner.

Practice, so always assisted and never evidence (ADR 0005): rows carry `assisted` = 1 and no study rate reads this ledger. The
question before the answer carries only the position, the side, the moves so far and the legal moves; the expected move is
named only after the answer (leak rule). Imports no LLM code. Book text is data only.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import chess

from app import config
from app.learner import repertoire

SCHEMA = """
CREATE TABLE IF NOT EXISTS rep_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, line TEXT NOT NULL, ply INTEGER NOT NULL,
  hits INTEGER NOT NULL DEFAULT 0, misses INTEGER NOT NULL DEFAULT 0, finished INTEGER NOT NULL DEFAULT 0,
  assisted INTEGER NOT NULL DEFAULT 1 CHECK (assisted = 1), started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS rep_node (
  key TEXT NOT NULL, prefix TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 0, misses INTEGER NOT NULL DEFAULT 0, last_at TEXT,
  PRIMARY KEY (key, prefix)
);
"""


class DrillError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def ledger_path() -> Path:
    return config.DATA_DIR / "repertoire" / "drills.sqlite3"


def connect() -> sqlite3.Connection:
    ledger_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ledger_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _our_prefixes(book: dict, line: list[str]) -> list[str]:
    side = book["side"]
    return [
        " ".join(line[:i])
        for i in range(len(line))
        if (("white" if i % 2 == 0 else "black") == side)
    ]


def _popularity(book: dict, line: list[str]) -> float:
    p = 1.0
    for i, san in enumerate(line):
        node = book["nodes"].get(" ".join(line[:i]))
        if node and "theirs" in node:
            p *= next((r["share"] for r in node["theirs"] if r["san"] == san), 1.0)
    return p


def pick_line(conn: sqlite3.Connection, key: str, book: dict, rng: random.Random) -> list[str]:
    """The line to drill next: misses first, then lines not yet seen, then the most common line. Ties are broken at random."""
    lines = [ln.split() for ln in repertoire.lines(book)]
    if not lines:
        raise DrillError("no_lines", f"the {key} book has no lines")
    stats = {
        r["prefix"]: (r["hits"], r["misses"])
        for r in conn.execute("SELECT prefix, hits, misses FROM rep_node WHERE key = ?", (key,))
    }

    def priority(line: list[str]) -> float:
        score = 0.0
        for prefix in _our_prefixes(book, line):
            hits, misses = stats.get(prefix, (0, 0))
            if hits + misses == 0:
                score += 1.0  # never asked
            else:
                score += 3.0 * misses / (hits + misses)
        return score + 0.5 * _popularity(book, line)

    best = max(priority(ln) for ln in lines)
    return rng.choice([ln for ln in lines if priority(ln) == best])


def _advance(book: dict, line: list[str], ply: int) -> int:
    """Play the opponent's moves from the line until it is the player's turn or the line ends."""
    while ply < len(line) and ("white" if ply % 2 == 0 else "black") != book["side"]:
        ply += 1
    return ply


def _board(history: list[str]) -> chess.Board:
    board = chess.Board()
    for san in history:
        board.push_san(san)
    return board


def _question(run_id: int, key: str, book: dict, line: list[str], ply: int) -> dict:
    board = _board(line[:ply])
    return {
        "run_id": run_id,
        "key": key,
        "name": book.get("name"),
        "side": book["side"],
        "fen": board.fen(),
        "ply": ply,
        "history": line[:ply],
        "legal": sorted(m.uci() for m in board.legal_moves),
        "assisted": True,
    }


def start(conn: sqlite3.Connection, key: str, book: dict, rng: random.Random | None = None) -> dict:
    line = pick_line(conn, key, book, rng or random.Random())
    ply = _advance(book, line, 0)
    cur = conn.execute(
        "INSERT INTO rep_run (key, line, ply, started_at) VALUES (?, ?, ?, ?)",
        (key, " ".join(line), ply, _now()),
    )
    conn.commit()
    return _question(cur.lastrowid, key, book, line, ply)


def answer(conn: sqlite3.Connection, run_id: int, uci: str, book: dict) -> dict:
    run = conn.execute("SELECT * FROM rep_run WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise DrillError("no_such_run", "that run does not exist")
    if run["finished"]:
        raise DrillError("run_finished", "that run is already finished")
    line, ply = run["line"].split(), run["ply"]
    board = _board(line[:ply])
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        move = None
    if move is None or move not in board.legal_moves:
        raise DrillError("illegal_move", f"{uci} is not a legal move here")
    expected = line[ply]
    matched = move == board.parse_san(expected)
    your_san = board.san(move)
    prefix = " ".join(line[:ply])
    conn.execute(
        "INSERT INTO rep_node (key, prefix, hits, misses, last_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(key, prefix) DO UPDATE SET hits = hits + excluded.hits, misses = misses + excluded.misses, last_at = excluded.last_at",
        (run["key"], prefix, 1 if matched else 0, 0 if matched else 1, _now()),
    )
    nxt = _advance(book, line, ply + 1)
    done = nxt >= len(line)
    hits, misses = run["hits"] + (1 if matched else 0), run["misses"] + (0 if matched else 1)
    conn.execute(
        "UPDATE rep_run SET ply = ?, hits = ?, misses = ?, finished = ?, finished_at = ? WHERE id = ?",
        (nxt, hits, misses, 1 if done else 0, _now() if done else None, run_id),
    )
    conn.commit()
    out = {
        "matched": matched,
        "expected_san": expected,
        "expected_uci": board.parse_san(expected).uci(),
        "your_san": your_san,
        "your_uci": move.uci(),
        "assisted": True,
        "next": None if done else _question(run_id, run["key"], book, line, nxt),
    }
    if done:
        out["summary"] = {"answered": hits + misses, "hits": hits, "misses": misses}
    return out


def stats(conn: sqlite3.Connection, key: str, book: dict) -> dict:
    lines = [ln.split() for ln in repertoire.lines(book)]
    ours = {p for ln in lines for p in _our_prefixes(book, ln)}
    rows = conn.execute(
        "SELECT prefix, hits, misses FROM rep_node WHERE key = ?", (key,)
    ).fetchall()
    return {
        "key": key,
        "lines": len(lines),
        "nodes_ours": len(ours),
        "nodes_seen": sum(1 for r in rows if r["prefix"] in ours),
        "hits": sum(r["hits"] for r in rows),
        "misses": sum(r["misses"] for r in rows),
        "assisted_only": True,
    }
