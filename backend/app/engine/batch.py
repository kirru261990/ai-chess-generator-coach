"""Fast engine pass over synced games (T10, spec B5).

Every position of every game is analysed once at a shallow budget. Results are
stored from White's point of view with the engine version and budget, so a game
is re-analysed only when either changes. Deep analysis is reserved for the few
positions a review flags.

Run: uv run python -m app.engine.batch [--limit N] [--depth D]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

import chess
import chess.pgn

from app import config
from app.engine.stockfish import Budget, Engine

BATCH_BUDGET = Budget(depth=10)


def game_id(source_id: str) -> str:
    """Short id for a Chess.com game: the last path segment of its URL."""
    return source_id.rstrip("/").rsplit("/", 1)[-1]


def parse_moves(pgn: str) -> tuple[chess.Board, list[chess.Move]] | None:
    """Mainline of a PGN, or None if it is unusable. PGN comments are ignored (untrusted)."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or game.errors or game.headers.get("Variant", "Standard") != "Standard":
        return None
    moves = list(game.mainline_moves())
    return (game.board(), moves) if moves else None


def analyse_game(engine: Engine, pgn: str, budget: Budget) -> dict | None:
    """Analyse every position (before move 1 .. after the last move), scores as White sees them."""
    parsed = parse_moves(pgn)
    if parsed is None:
        return None
    board, moves = parsed
    positions, sans = [], []
    for i in range(len(moves) + 1):
        a = engine.analyse(board, budget, perspective=chess.WHITE)
        positions.append(
            {
                "ply": i,
                "fen": board.fen(),
                "cp": a.score.cp,
                "mate": a.score.mate,
                "best": a.best_move,
                "depth": a.depth,
            }
        )
        if i < len(moves):
            sans.append(board.san(moves[i]))
            board.push(moves[i])
    return {
        "engine": engine.name,
        "budget": {"depth": budget.depth, "movetime_ms": budget.movetime_ms},
        "moves": [m.uci() for m in moves],
        "sans": sans,
        "positions": positions,
    }


class AnalysisStore:
    """JSON-lines store under data/ (git-ignored): one record per analysed game."""

    def __init__(self, path: Path):
        self.path = path
        self._records: dict[str, dict] = {}
        if path.exists():
            with path.open() as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        self._records[r["source_id"]] = r

    def has(self, source_id: str, engine: str, budget: Budget) -> bool:
        r = self._records.get(source_id)
        want = {"depth": budget.depth, "movetime_ms": budget.movetime_ms}
        return bool(r and r["engine"] == engine and r["budget"] == want)

    def get(self, source_id: str) -> dict | None:
        return self._records.get(source_id)

    def add(self, source_id: str, analysis: dict) -> None:
        record = {"source_id": source_id, **analysis}
        self._records[source_id] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:  # latest line per source_id wins on reload
            f.write(json.dumps(record) + "\n")

    def __len__(self) -> int:
        return len(self._records)


def run_batch(
    games: list[dict],
    store: AnalysisStore,
    engine: Engine,
    budget: Budget = BATCH_BUDGET,
    limit: int | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Analyse games not yet analysed at this engine + budget. Resumable: safe to interrupt."""
    todo = [g for g in games if not store.has(g["source_id"], engine.name, budget)]
    skipped_done = len(games) - len(todo)
    if limit is not None:
        todo = todo[:limit]
    done = unusable = 0
    for n, g in enumerate(todo, 1):
        result = analyse_game(engine, g["pgn"], budget)
        if result is None:
            unusable += 1
        else:
            store.add(g["source_id"], result)
            done += 1
        if progress:
            progress(n, len(todo), g["source_id"])
    return {"analysed": done, "unusable": unusable, "already_done": skipped_done}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=None, help="analyse at most N games this run")
    ap.add_argument("--depth", type=int, default=BATCH_BUDGET.depth)
    args = ap.parse_args(argv)
    username = config.chesscom_username()
    if not username:
        sys.exit("set CHESSCOM_USERNAME in .env")
    games_path = config.DATA_DIR / "games" / f"chesscom_{username.lower()}.jsonl"
    if not games_path.exists():
        sys.exit("no synced games; run: uv run python -m app.sync")
    games = [json.loads(line) for line in games_path.read_text().splitlines() if line.strip()]
    games.sort(key=lambda g: g["end_time"], reverse=True)  # newest first
    store = AnalysisStore(config.DATA_DIR / "analysis" / f"chesscom_{username.lower()}.jsonl")
    start = time.time()

    def progress(n: int, total: int, sid: str) -> None:
        rate = (time.time() - start) / n
        print(f"[{n}/{total}] {game_id(sid)}  ~{rate * (total - n) / 60:.1f} min left", flush=True)

    with Engine() as engine:
        print(json.dumps(run_batch(games, store, engine, Budget(depth=args.depth), args.limit, progress)))


if __name__ == "__main__":
    main()
