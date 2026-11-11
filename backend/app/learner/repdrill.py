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
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, book_id TEXT NOT NULL, line TEXT NOT NULL, ply INTEGER NOT NULL,
  hits INTEGER NOT NULL DEFAULT 0, misses INTEGER NOT NULL DEFAULT 0, finished INTEGER NOT NULL DEFAULT 0,
  learn INTEGER NOT NULL DEFAULT 1, shown INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
  missed_ply INTEGER NOT NULL DEFAULT -1,
  assisted INTEGER NOT NULL DEFAULT 1 CHECK (assisted = 1), started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS rep_node (
  key TEXT NOT NULL, position TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 0, misses INTEGER NOT NULL DEFAULT 0,
  shown INTEGER NOT NULL DEFAULT 0, last_at TEXT,
  PRIMARY KEY (key, position)
);
"""


class DrillError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def ledger_path() -> Path:
    return (
        config.DATA_DIR / "repertoire" / "drills_v2.sqlite3"
    )  # v2: positions, not move-order prefixes


def connect() -> sqlite3.Connection:
    ledger_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ledger_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for table, cols in (
        (
            "rep_run",
            (
                "learn INTEGER NOT NULL DEFAULT 1",
                "shown INTEGER NOT NULL DEFAULT 0",
                "attempts INTEGER NOT NULL DEFAULT 0",
                "missed_ply INTEGER NOT NULL DEFAULT -1",
            ),
        ),
        ("rep_node", ("shown INTEGER NOT NULL DEFAULT 0",)),
    ):  # a ledger made before learn mode gets the new columns; its old rows keep the defaults
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col in cols:
            if col.split()[0] not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _our_positions(book: dict, line: list[str]) -> list[str]:
    """The position key before each of our moves in the line."""
    board, out = chess.Board(), []
    for i, san in enumerate(line):
        if repertoire.mover_at(i) == book["side"]:
            out.append(repertoire.pos_key(board))
        board.push_san(san)
    return out


def _popularity(book: dict, line: list[str]) -> float:
    p, board = 1.0, chess.Board()
    for san in line:
        node = book["nodes"].get(repertoire.pos_key(board))
        if node and "theirs" in node:
            share = next((r["share"] for r in node["theirs"] if r["san"] == san), None)
            p *= share if share is not None else 1.0  # an engine move carries no share
        board.push_san(san)
    return p


def pick_line(conn: sqlite3.Connection, key: str, book: dict, rng: random.Random) -> list[str]:
    """The line to drill next: misses first, then lines not yet seen, then the most common line. Ties are broken at random."""
    lines = repertoire.lines(book)
    if not lines:
        raise DrillError("no_lines", f"the {key} book has no lines")
    stats = {
        r["position"]: (r["hits"], r["misses"], r["shown"])
        for r in conn.execute(
            "SELECT position, hits, misses, shown FROM rep_node WHERE key = ?", (key,)
        )
    }

    def priority(line: list[str]) -> float:
        score = 0.0
        for position in _our_positions(book, line):
            hits, misses, shown = stats.get(position, (0, 0, 0))
            if hits + misses > 0:
                score += 3.0 * misses / (hits + misses)  # how often it was missed
            else:
                score += (
                    0.5 if shown else 1.0
                )  # only shown with the arrow counts as half known; never seen counts in full
        return score + 0.5 * _popularity(book, line)

    best = max(priority(ln) for ln in lines)
    return rng.choice([ln for ln in lines if priority(ln) == best])


def _advance(book: dict, line: list[str], ply: int) -> int:
    """Play the opponent's moves from the line until it is the player's turn or the line ends."""
    while ply < len(line) and repertoire.mover_at(ply) != book["side"]:
        ply += 1
    return ply


def _question(run_id: int, key: str, book: dict, line: list[str], ply: int, learn: bool) -> dict:
    """The position to answer. Only a learn run shows the move (as `arrow`); a recall run names nothing before the answer."""
    board = repertoire.board_after(line[:ply])
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
        "source": book["nodes"].get(repertoire.pos_key(board), {}).get("source", "players"),
        "learn": learn,
        "arrow": board.parse_san(line[ply]).uci() if learn else None,
    }


def start(
    conn: sqlite3.Connection,
    key: str,
    book: dict,
    rng: random.Random | None = None,
    learn: bool = True,
) -> dict:
    """Start a run. `learn` shows the move as an arrow (to learn a line); without it the player must recall it."""
    if not repertoire.is_checked(book):
        raise DrillError(
            "book_unchecked",
            "this book was built without the engine check, so it is not used for drills",
        )
    line = pick_line(conn, key, book, rng or random.Random())
    ply = _advance(book, line, 0)
    cur = conn.execute(
        "INSERT INTO rep_run (key, book_id, line, ply, learn, started_at) VALUES (?, ?, ?, ?, ?, ?)",
        (key, book["id"], " ".join(line), ply, 1 if learn else 0, _now()),
    )
    conn.commit()
    return _question(cur.lastrowid, key, book, line, ply, learn)


REVEAL_AFTER = 2  # wrong tries on one position before a recall run shows the move


def _count(conn: sqlite3.Connection, key: str, position: str, col: str) -> None:
    conn.execute(
        f"INSERT INTO rep_node (key, position, {col}, last_at) VALUES (?, ?, 1, ?) "
        f"ON CONFLICT(key, position) DO UPDATE SET {col} = {col} + 1, last_at = excluded.last_at",
        (key, position, _now()),
    )


def answer(
    conn: sqlite3.Connection, run_id: int, uci: str, book: dict, key: str | None = None
) -> dict:
    """One try at the position. A wrong move does not move the line on: the player tries again (the board shows a cross and the
    piece stays). In a recall run the first wrong try on a position counts as one miss, and a right first try as one hit; in a learn
    run nothing is counted as right or wrong, because the arrow showed the move."""
    run = conn.execute("SELECT * FROM rep_run WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise DrillError("no_such_run", "that run does not exist")
    if key is not None and run["key"] != key:
        raise DrillError("run_key_mismatch", f"that run belongs to {run['key']}, not {key}")
    if run["book_id"] != book["id"]:
        raise DrillError(
            "book_changed", "the book was rebuilt since this run started; start a new run"
        )
    if run["finished"]:
        raise DrillError("run_finished", "that run is already finished")
    line, ply, learn = run["line"].split(), run["ply"], bool(run["learn"])
    board = repertoire.board_after(line[:ply])
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        move = None
    if move is None or move not in board.legal_moves:
        raise DrillError("illegal_move", f"{uci} is not a legal move here")
    expected = line[ply]
    expected_uci = board.parse_san(expected).uci()
    matched = move.uci() == expected_uci
    position = repertoire.pos_key(board)
    base = {
        "matched": matched,
        "your_san": board.san(move),
        "your_uci": move.uci(),
        "assisted": True,
        "learn": learn,
    }
    if not matched:
        attempts = run["attempts"] + 1
        misses = run["misses"]
        missed_ply = run["missed_ply"]
        if (
            not learn and missed_ply != ply
        ):  # the first wrong try on this position is the miss; more tries add nothing
            _count(conn, run["key"], position, "misses")
            misses, missed_ply = misses + 1, ply
        conn.execute(
            "UPDATE rep_run SET attempts = ?, misses = ?, missed_ply = ? WHERE id = ?",
            (attempts, misses, missed_ply, run_id),
        )
        conn.commit()
        show = learn or attempts >= REVEAL_AFTER
        return base | {
            "retry": True,
            "attempts": attempts,
            "next": None,
            "expected_san": expected if show else None,
            "expected_uci": expected_uci if show else None,
        }
    hits, shown = run["hits"], run["shown"]
    if learn:
        _count(conn, run["key"], position, "shown")
        shown += 1
    elif run["missed_ply"] != ply:  # right at the first try
        _count(conn, run["key"], position, "hits")
        hits += 1
    nxt = _advance(book, line, ply + 1)
    done = nxt >= len(line)
    conn.execute(
        "UPDATE rep_run SET ply = ?, hits = ?, shown = ?, attempts = 0, finished = ?, finished_at = ? WHERE id = ?",
        (nxt, hits, shown, 1 if done else 0, _now() if done else None, run_id),
    )
    conn.commit()
    out = base | {
        "retry": False,
        "attempts": run["attempts"],
        "expected_san": expected,
        "expected_uci": expected_uci,
        "next": None if done else _question(run_id, run["key"], book, line, nxt, learn),
    }
    if done:
        out["summary"] = {
            "answered": hits + run["misses"] + shown,
            "hits": hits,
            "misses": run["misses"],
            "shown": shown,
        }
    return out


def stats(conn: sqlite3.Connection, key: str, book: dict) -> dict:
    lines = repertoire.lines(book)
    ours = {p for ln in lines for p in _our_positions(book, ln)}
    engine = {p for p in ours if book["nodes"].get(p, {}).get("source") == "engine"}
    rows = conn.execute(
        "SELECT position, hits, misses, shown FROM rep_node WHERE key = ?", (key,)
    ).fetchall()
    return {
        "key": key,
        "lines": len(lines),
        "nodes_ours": len(ours),
        "nodes_engine": len(engine),
        "nodes_seen": sum(
            1 for r in rows if r["position"] in ours and r["hits"] + r["misses"] + r["shown"] > 0
        ),
        "nodes_recalled": sum(
            1 for r in rows if r["position"] in ours and r["hits"] + r["misses"] > 0
        ),
        "hits": sum(r["hits"] for r in rows),
        "misses": sum(r["misses"] for r in rows),
        "assisted_only": True,
    }
