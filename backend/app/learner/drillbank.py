"""Drill library from public Lichess games (ADR 0017): middlegame positions where the side to move made a move the detectors
call a mistake, verified by the pinned evidence engine.

Run (from backend/; needs Stockfish 19 as in `evidence_run`):
  uv run python -m app.learner.drillbank build --pgn PATH [--limit N] [--workers 4] [--types M1,M2]   # resumable
  uv run python -m app.learner.drillbank summary

Output (git-ignored): data/drills/drillbank_v1.jsonl, one drill per line, and data/drills/cache.sqlite3 (engine cache).
Counts are yields, not error rates: a shallow prefilter drops moves that lose less than PREFILTER_LOSS_CP (ADR 0017 decision 6).
Imports no LLM code. PGN text is data only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import multiprocessing as mp
import sys
from collections import Counter
from pathlib import Path

import chess
import chess.pgn

from app import config
from app.db.schema import connect
from app.detectors import hanging_own_v4, missed_free_v3, missed_threat
from app.detectors import prd_rules as R

BANK_VERSION = "1"
MIN_PLY, MAX_PLY = 12, 60
MIN_PIECES_EACH = 3  # knights, bishops, rooks, queens; not the king or pawns
PREFILTER_DEPTH = 10
PREFILTER_LOSS_CP = 100
DEFAULT_TYPES = ("M1", "M2")  # M3 is experimental until it passes a real-game check (ADR 0015, 0017 decision 5)
DETECTORS = {"M1": hanging_own_v4, "M2": missed_free_v3, "M3": missed_threat}
DRILL_OUTCOME = {"M1": "mistake", "M2": "missed", "M3": "missed"}  # the outcome each detector uses for a real error


def bank_dir() -> Path:
    return config.DATA_DIR / "drills"


def bank_path() -> Path:
    return bank_dir() / f"drillbank_v{BANK_VERSION}.jsonl"


def cache_path() -> Path:
    return bank_dir() / "cache.sqlite3"


def pieces_besides_pawns(board: chess.Board, color: chess.Color) -> int:
    return sum(len(board.pieces(pt, color)) for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))


def in_middlegame(board: chess.Board, ply: int) -> bool:
    """ADR 0017 decision 3: `board` is the position before the move at half-move index `ply`."""
    if not MIN_PLY <= ply <= MAX_PLY:
        return False
    return all(pieces_besides_pawns(board, c) >= MIN_PIECES_EACH for c in (chess.WHITE, chess.BLACK))


def game_info(game: chess.pgn.Game) -> dict:
    h = game.headers
    try:
        ratings = (int(h["WhiteElo"]), int(h["BlackElo"]))
    except (KeyError, ValueError):
        ratings = None
    site = h.get("Site", "")
    return {"game_id": site.rsplit("/", 1)[-1] or None, "avg_rating": round(sum(ratings) / 2) if ratings else None}


def drill_id(fen: str, move: str, mtype: str) -> str:
    return hashlib.sha256(f"{fen}|{move}|{mtype}".encode()).hexdigest()[:16]


def lost_cp(board: chess.Board, move: chess.Move, analyser) -> int | None:
    """Shallow loss for the mover (centipawns), or None when the move ends the game or nothing could be searched."""
    mover = board.turn
    before = analyser.analyse(board, depth=PREFILTER_DEPTH).best
    nxt = board.copy(stack=False)
    nxt.push(move)
    if before is None or nxt.is_game_over():
        return None
    after = analyser.analyse(nxt, depth=PREFILTER_DEPTH).best
    if after is None:
        return None
    return R.line_score(before, mover) - R.line_score(after, mover)


def scan_game(pgn: str, analyser, types=DEFAULT_TYPES, stats: Counter | None = None) -> list[dict]:
    """Drills found in one game, both players' moves. Raises ValueError when the PGN cannot be read."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or game.errors:
        raise ValueError("the PGN could not be read")
    info = game_info(game)
    stats = stats if stats is not None else Counter()
    out: list[dict] = []
    board = game.board()
    previous: chess.Board | None = None
    for ply, node in enumerate(game.mainline()):
        move = node.move
        if in_middlegame(board, ply):
            stats["middlegame_moves"] += 1
            loss = lost_cp(board, move, analyser)
            if loss is not None and loss >= PREFILTER_LOSS_CP:
                stats["candidates"] += 1
                for t in types:
                    det = DETECTORS[t]
                    if t == "M3":
                        finding = det.detect(board, move, ply, analyser, previous=previous)
                    else:
                        finding = det.detect(board, move, ply, analyser)
                    stats[f"{t}:{finding.outcome}"] += 1
                    if finding.outcome == DRILL_OUTCOME[t]:
                        fen = board.fen()
                        out.append({
                            "id": drill_id(fen, move.uci(), t), "type": t, "fen": fen, "ply": ply,
                            "side": "white" if board.turn else "black", "played": move.uci(),
                            "played_san": board.san(move), **info, "evidence": finding.evidence,
                            "alternatives": list(getattr(finding, "alternatives", ())), "source": "lichess",
                            "experimental": t == "M3",
                            "versions": {"bank": BANK_VERSION, "detector": f"{det.DETECTOR}:{det.VERSION}",
                                         "rules": R.RULES_VERSION, "engine_config": analyser.config.id},
                        })
        previous = board.copy(stack=False)  # for the next ply this is the position before the opponent's last move
        board.push(move)
    return out


def read_games(path: Path):
    """Yield (game id, pgn text) from a PGN file of many games."""
    with path.open(encoding="utf-8", errors="replace") as f:
        while (g := chess.pgn.read_game(f)) is not None:
            yield game_info(g)["game_id"], str(g)


_worker: dict = {}


def _init_worker(db_path: str) -> None:
    from app.engine.evidence import open_evidence

    ctx = open_evidence(connect(db_path))
    _worker["analyser"], _worker["ctx"] = ctx.__enter__(), ctx


def _process(task: tuple[str, str, tuple[str, ...]]) -> dict:
    gid, pgn, types = task
    stats: Counter = Counter()
    try:
        return {"game": gid, "types": types, "drills": scan_game(pgn, _worker["analyser"], types, stats), "stats": dict(stats), "error": None}
    except ValueError as e:  # one unreadable game must not stop the run
        return {"game": gid, "types": types, "drills": [], "stats": {}, "error": str(e)}


def done_games(path: Path) -> set[tuple[str, str]]:
    """(game id, drill type) pairs already scanned. A line with only a game id comes from before types were tracked: M1 and M2."""
    marker = path.with_suffix(".done")
    out: set[tuple[str, str]] = set()
    for line in marker.read_text().splitlines() if marker.exists() else []:
        gid, *types = line.split()
        out.update((gid, t) for t in (types or DEFAULT_TYPES))
    return out


def build(pgn: Path, limit: int | None, workers: int, types=DEFAULT_TYPES) -> dict:
    bank_dir().mkdir(parents=True, exist_ok=True)
    out, marker = bank_path(), bank_path().with_suffix(".done")
    seen = done_games(out)
    tasks = []
    for gid, text in read_games(pgn):
        todo = tuple(t for t in types if (gid, t) not in seen)
        if gid and todo:
            tasks.append((gid, text, todo))
        if limit and len(tasks) >= limit:
            break
    stats: Counter = Counter()
    added = errors = 0
    with mp.get_context("spawn").Pool(workers, _init_worker, (str(cache_path()),)) as pool, \
            out.open("a") as f, marker.open("a") as m:
        for i, r in enumerate(pool.imap_unordered(_process, tasks), 1):
            stats.update(r["stats"])
            errors += bool(r["error"])
            for d in r["drills"]:
                f.write(json.dumps(d, default=str) + "\n")
                added += 1
            if not r["error"]:
                m.write(f"{r['game']} {' '.join(r['types'])}\n")
            f.flush(), m.flush()
            if i % 10 == 0:
                print(f"{i}/{len(tasks)} games, {added} drills", file=sys.stderr, flush=True)
    return {"games": len(tasks), "errors": errors, "drills_added": added, "stats": dict(stats)}


def summary(path: Path | None = None) -> dict:
    path = path or bank_path()
    drills = [json.loads(line) for line in path.open()] if path.exists() else []
    by_band = Counter((d["avg_rating"] // 200 * 200) if d["avg_rating"] else None for d in drills)
    return {"drills": len(drills), "games_scanned": len({g for g, _ in done_games(path)}), "by_type": dict(Counter(d["type"] for d in drills)),
            "by_rating_band": {str(k): v for k, v in sorted(by_band.items(), key=lambda kv: (kv[0] is None, kv[0]))},
            "by_side": dict(Counter(d["side"] for d in drills))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="drillbank")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--pgn", type=Path, required=True)
    b.add_argument("--limit", type=int)
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--types", default=",".join(DEFAULT_TYPES))
    sub.add_parser("summary")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(json.dumps(build(a.pgn, a.limit, a.workers, tuple(a.types.split(","))), indent=1))
    else:
        print(json.dumps(summary(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
