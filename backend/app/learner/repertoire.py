"""Repertoire lines for one opening (ADR 0022): what to play, what players really answer, checked by the engine.

Built from the move-prefix counts in `openingtrie`. At our turn the move is the most played one that the pinned evidence engine
does not reject (a move more than ENGINE_FLOOR_CP worse than the best is never kept, rule 2). At the opponent's turn every reply
with at least MIN_SHARE of the games at that position is kept, while the branch still holds at least MIN_LINE_SHARE of all the
opening's games (and at least MIN_LINE_GAMES games). Imports no LLM code. Move text is data only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chess

from app import config
from app.detectors import prd_rules as R

VERSION = "1"
MIN_SHARE = 0.06  # of the games at that position
MIN_LINE_SHARE = 0.003  # of all the opening's games
MIN_LINE_GAMES = 5  # and never fewer than this many games, so a line is not built on a handful
ENGINE_FLOOR_CP = 50
MAX_PLIES = 20


def _children(counts: dict[tuple[str, ...], int], prefix: tuple[str, ...]) -> list[tuple[str, int]]:
    n = len(prefix)
    kids = [(p[-1], c) for p, c in counts.items() if len(p) == n + 1 and p[:n] == prefix]
    return sorted(kids, key=lambda k: (-k[1], k[0]))  # most played first, ties alphabetical


def _board(prefix: tuple[str, ...]) -> chess.Board:
    board = chess.Board()
    for san in prefix:
        board.push_san(san)
    return board


def _check(
    analyser, board: chess.Board, san: str, depth: int
) -> tuple[bool, int | None, str | None]:
    """(passes, gap in cp, engine's best move in UCI). The gap is best minus the move's score for the mover; a played move that is
    not among the engine's lines is scored by searching the position after it."""
    mover = board.turn
    analysis = analyser.analyse(board, depth=depth)
    if analysis.best is None:
        return False, None, None
    best = R.line_score(analysis.best, mover)
    move = board.parse_san(san)
    for ln in analysis.lines:
        if ln.move == move.uci():
            gap = best - R.line_score(ln, mover)
            return gap <= ENGINE_FLOOR_CP, gap, analysis.best.move
    after = board.copy(stack=True)
    after.push(move)
    scored = analyser.analyse(after, depth=depth)
    if scored.best is None:
        return False, None, analysis.best.move
    gap = best - R.line_score(scored.best, mover)
    return gap <= ENGINE_FLOOR_CP, gap, analysis.best.move


def build(opening: dict, engine=None, depth: int = 18, max_plies: int = MAX_PLIES) -> dict:
    """The book for one opening document from `openingtrie.load(...)["openings"][key]`.

    `nodes` maps a move prefix ("e4 c6", "" for the start) to {mover, ours | theirs, check?}. `stopped` lists the places where no
    played move passed the engine check, so the line ends there instead of showing an unverified move.
    """
    side = opening["side"]
    games = opening["games"]
    counts = {tuple(line.split()): n for line, n in opening["lines"]}
    nodes: dict[str, dict] = {}
    stopped: list[dict] = []

    def walk(prefix: tuple[str, ...]) -> None:
        if len(prefix) >= max_plies:
            return
        mover = "white" if len(prefix) % 2 == 0 else "black"
        kids = _children(counts, prefix)
        if not kids:
            return
        key = " ".join(prefix)
        here = games if not prefix else counts.get(prefix, 0)
        if mover == side:
            chosen = None
            for san, _ in kids:
                if engine is None:
                    chosen = (san, {"status": "unchecked"})
                    break
                ok, gap, _best = _check(engine, _board(prefix), san, depth)
                if ok:
                    status = "ok" if san == kids[0][0] else "replaced"
                    chosen = (san, {"status": status, "gap_cp": gap, "depth": depth})
                    break
            if chosen is None:
                stopped.append(
                    {"prefix": key, "reason": f"no_played_move_within_{ENGINE_FLOOR_CP}cp"}
                )
                return
            nodes[key] = {"mover": mover, "ours": chosen[0], "check": chosen[1]}
            walk(prefix + (chosen[0],))
            return
        replies = [
            {"san": san, "count": n, "share": n / here}
            for san, n in kids
            if here and n / here >= MIN_SHARE and n >= max(MIN_LINE_GAMES, MIN_LINE_SHARE * games)
        ]
        if not replies:
            return
        nodes[key] = {"mover": mover, "theirs": replies}
        for r in replies:
            walk(prefix + (r["san"],))

    walk(())
    return {
        "version": VERSION,
        "side": side,
        "name": opening.get("name"),
        "games": games,
        "max_plies": max_plies,
        "min_share": MIN_SHARE,
        "min_line_share": MIN_LINE_SHARE,
        "engine_floor_cp": ENGINE_FLOOR_CP,
        "nodes": nodes,
        "stopped": stopped,
    }


def lines(book: dict) -> list[str]:
    """Every line the book reaches to its end, as SAN move strings."""
    out: list[str] = []

    def go(prefix: tuple[str, ...]) -> None:
        node = book["nodes"].get(" ".join(prefix))
        nxt = (
            [node["ours"]]
            if node and "ours" in node
            else [r["san"] for r in node["theirs"]]
            if node
            else []
        )
        if not nxt:
            if prefix:
                out.append(" ".join(prefix))
            return
        for san in nxt:
            go(prefix + (san,))

    go(())
    return out


def book_path(key: str) -> Path:
    return config.DATA_DIR / "repertoire" / f"book_{key}_v{VERSION}.json"


def save_book(key: str, book: dict) -> Path:
    path = book_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(book, indent=1) + "\n")
    tmp.replace(path)
    return path


def load_book(key: str) -> dict | None:
    path = book_path(key)
    return json.loads(path.read_text()) if path.exists() else None


def main() -> None:
    from app.learner import openingtrie

    ap = argparse.ArgumentParser(
        description="Build repertoire books from opening counts (run `openingtrie build` first)."
    )
    ap.add_argument(
        "--counts", required=True, help="data/repertoire/openings_<month>_<low>_<high>.json"
    )
    ap.add_argument("--opening", help="one key, e.g. caro_kann (default: all five)")
    ap.add_argument(
        "--no-engine",
        action="store_true",
        help="skip the engine check (moves are marked unchecked)",
    )
    ap.add_argument("--depth", type=int, default=18)
    a = ap.parse_args()
    data = openingtrie.load(Path(a.counts))
    keys = [a.opening] if a.opening else list(data["openings"])
    if a.no_engine:
        run = [(k, None) for k in keys]
        ctx = None
    else:
        from app.db.schema import connect
        from app.engine.evidence import open_evidence

        cache = config.DATA_DIR / "repertoire" / "engine_cache.sqlite3"
        cache.parent.mkdir(parents=True, exist_ok=True)
        ctx = open_evidence(connect(str(cache)))
        analyser = ctx.__enter__()
        run = [(k, analyser) for k in keys]
    try:
        for key, analyser in run:
            book = build(data["openings"][key], engine=analyser, depth=a.depth)
            book["source"] = {
                "counts": Path(a.counts).name,
                "month": data["month"],
                "band": data["band"],
                "licence": data["licence"],
            }
            path = save_book(key, book)
            print(
                key,
                f"{len(book['nodes'])} nodes, {len(lines(book))} lines, {len(book['stopped'])} stopped ->",
                path,
            )
    finally:
        if ctx is not None:
            ctx.__exit__(None, None, None)


if __name__ == "__main__":
    main()
