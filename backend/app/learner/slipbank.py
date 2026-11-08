"""Build first-slip drills (ADR 0020) from the owner's games ("own") or a public Lichess PGN ("lichess", fresh drills).

Run (from backend/; needs Stockfish 19 as in `evidence_run`):
  uv run python -m app.learner.slipbank build --source own [--limit N] [--workers 4]
  uv run python -m app.learner.slipbank build --source lichess --pgn PATH [--limit N] [--workers 4]
  uv run python -m app.learner.slipbank summary

Output (git-ignored): data/drills/slips_v1.jsonl, one drill per line, and slips_v1.done (games already scanned; resumable). Counts are
yields, not error rates. Imports no LLM code. PGN text is data only.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
from collections import Counter
from pathlib import Path

import chess
import chess.pgn

from app import config
from app.db.schema import connect
from app.learner import drillbank, slipfinder, slipround


def scan_pgn(pgn: str, analyser, source: str, color: chess.Color | None = None, game_id: str | None = None) -> dict | None:
    """The first-slip drill of one game, or None (no slip, or an unclear position). Raises ValueError for an unreadable PGN."""
    import io

    info = drillbank.game_info(chess.pgn.read_game(io.StringIO(pgn)))
    found = slipfinder.find_first_slip(pgn, analyser, color)
    if found["status"] != "slip":
        return None
    return slipfinder.to_drill(found["slip"], game_id or info["game_id"], info["avg_rating"], source)


def cache_path() -> Path:
    return drillbank.bank_dir() / "slip_cache.sqlite3"


def done_path() -> Path:
    return slipround.slips_path().with_suffix(".done")


def own_games():
    """Yield (game id, pgn, colour) from the synced Chess.com file."""
    path = config.DATA_DIR / "games" / f"chesscom_{(config.chesscom_username() or '').lower()}.jsonl"
    for line in path.open():
        g = json.loads(line)
        yield g["source_id"].rsplit("/", 1)[-1], g["pgn"], chess.WHITE if g["user_color"] == "white" else chess.BLACK


def public_games(path: Path):
    with path.open(encoding="utf-8", errors="replace") as f:
        while (g := chess.pgn.read_game(f)) is not None:
            yield drillbank.game_info(g)["game_id"], str(g), None


_worker: dict = {}


def _init_worker(db_path: str) -> None:
    from app.engine.evidence import open_evidence

    ctx = open_evidence(connect(db_path))
    _worker["analyser"], _worker["ctx"] = ctx.__enter__(), ctx


def _process(task: tuple) -> dict:
    gid, pgn, color, source = task
    try:
        return {"game": gid, "drill": scan_pgn(pgn, _worker["analyser"], source, color, gid), "error": None}
    except ValueError as e:  # one unreadable game must not stop the run
        return {"game": gid, "drill": None, "error": str(e)}


def build(source: str, pgn: Path | None, limit: int | None, workers: int) -> dict:
    drillbank.bank_dir().mkdir(parents=True, exist_ok=True)
    out, marker = slipround.slips_path(), done_path()
    seen = set(marker.read_text().split()) if marker.exists() else set()
    games = own_games() if source == "own" else public_games(pgn)
    tasks = []
    for gid, text, color in games:
        key = f"{source}:{gid}"
        if gid and key not in seen:
            tasks.append((gid, text, color, source))
        if limit and len(tasks) >= limit:
            break
    added = errors = 0
    connect(str(cache_path())).close()  # create the cache once, so the workers do not race to make it
    with mp.get_context("spawn").Pool(workers, _init_worker, (str(cache_path()),)) as pool, out.open("a") as f, marker.open("a") as m:
        for i, r in enumerate(pool.imap_unordered(_process, tasks), 1):
            errors += bool(r["error"])
            if r["drill"]:
                f.write(json.dumps(r["drill"], default=str) + "\n")
                added += 1
            if not r["error"]:
                m.write(f"{source}:{r['game']}\n")
            f.flush(), m.flush()
            if i % 10 == 0:
                print(f"{i}/{len(tasks)} games, {added} drills", file=sys.stderr, flush=True)
    return {"games": len(tasks), "errors": errors, "drills_added": added}


def summary() -> dict:
    p = slipround.slips_path()
    drills = [json.loads(line) for line in p.open()] if p.exists() else []
    return {"drills": len(drills), "by_source": dict(Counter(d["source"] for d in drills)),
            "median_move": sorted(d["ply"] // 2 + 1 for d in drills)[len(drills) // 2] if drills else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="slipbank")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--source", choices=("own", "lichess"), required=True)
    b.add_argument("--pgn", type=Path)
    b.add_argument("--limit", type=int)
    b.add_argument("--workers", type=int, default=4)
    sub.add_parser("summary")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        if a.source == "lichess" and not a.pgn:
            ap.error("--pgn is required for --source lichess")
        print(json.dumps(build(a.source, a.pgn, a.limit, a.workers), indent=1))
    else:
        print(json.dumps(summary(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
