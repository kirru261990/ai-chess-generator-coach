"""Repertoire books for one opening (ADR 0022): what to play, what players really answer, then engine-led play into the middlegame.

Built from the move-prefix counts in `openingtrie`. Books are keyed by *position*, not move order, so a transposition is one
node with one answer. At our turn the move is the most played one that the pinned evidence engine does not reject (a move more than
ENGINE_FLOOR_CP worse than the best is never kept, rule 2). At the opponent's turn every reply with at least MIN_SHARE of the games
at that position is kept, while the branch still holds at least MIN_LINE_SHARE of all the opening's games (and MIN_LINE_GAMES games).
Where the players' games run out, the line goes on with the engine's best move for both sides up to ENGINE_MAX_PLIES; those nodes are
marked `source: "engine"` and are not what most players at this level play. Imports no LLM code. Move text is data only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import chess

from app import config
from app.detectors import prd_rules as R

VERSION = "2"  # position-keyed books with engine continuations; version 1 was keyed by move order
MIN_SHARE = 0.06  # of the games at that position
MIN_LINE_SHARE = 0.003  # of all the opening's games
MIN_LINE_GAMES = 5  # and never fewer than this many games, so a line is not built on a handful
ENGINE_FLOOR_CP = 50
MAX_PLIES = 20  # how far the players' games are followed
ENGINE_MAX_PLIES = 40  # how far the engine continues a line (Black's 20th move, the owner's choice)


def pos_key(board: chess.Board) -> str:
    """The position without move counters: the same position reached by a different move order has the same key."""
    return " ".join(board.fen().split()[:4])


def mover_at(ply: int) -> str:
    return "white" if ply % 2 == 0 else "black"


def board_after(history: list[str] | tuple[str, ...]) -> chess.Board:
    board = chess.Board()
    for san in history:
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


def _engine_record(engine, depth: int) -> dict | None:
    if engine is None:
        return None
    cfg = getattr(engine, "config", None)
    return {
        "version": getattr(cfg, "version", None),
        "network": getattr(cfg, "network", None),
        "depth": depth,
        "multipv": getattr(cfg, "multipv", None),
        "config_id": getattr(cfg, "id", None),
        "floor_cp": ENGINE_FLOOR_CP,
    }


def _aggregate(opening: dict) -> tuple[dict, dict]:
    """(position counts, edges) from the move-prefix counts. Two prefixes that reach the same position are different
    games, so their counts add."""
    prefixes = sorted(
        ((tuple(line.split()), n) for line, n in opening["lines"]), key=lambda x: len(x[0])
    )
    start = chess.Board()
    boards: dict[tuple[str, ...], chess.Board] = {(): start}
    pos_n: dict[str, int] = defaultdict(int)
    pos_n[pos_key(start)] = opening["games"]
    edges: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for prefix, n in prefixes:
        parent = boards.get(prefix[:-1])
        if parent is None:
            continue  # a prefix whose parent was not saved (count under the saved minimum) cannot be placed
        board = parent.copy(stack=False)
        try:
            board.push_san(prefix[-1])
        except ValueError:
            continue  # a move the rules do not allow is data noise, never a book move
        boards[prefix] = board
        pk, parent_pk = pos_key(board), pos_key(parent)
        pos_n[pk] += n
        edges[parent_pk][prefix[-1]] += n
    return pos_n, edges


def build(
    opening: dict,
    engine=None,
    depth: int = 18,
    max_plies: int = MAX_PLIES,
    engine_plies: int = ENGINE_MAX_PLIES,
) -> dict:
    """The book for one opening document from `openingtrie.load(...)["openings"][key]`.

    `nodes` maps a position key to {fen, mover, ours | theirs, check?, source}. `stopped` lists the places where no played move passed
    the engine check, so the line ends there instead of showing an unverified move. Without an engine nothing is checked (every move
    is marked unchecked) and no engine continuation is added.
    """
    side = opening["side"]
    games = opening["games"]
    pos_n, edges = _aggregate(opening)
    nodes: dict[str, dict] = {}
    stopped: list[dict] = []
    seen: set[str] = set()
    floor = max(MIN_LINE_GAMES, MIN_LINE_SHARE * games)

    def extend_with_engine(board: chess.Board, ply: int) -> None:
        """Go on from where the players' games ran out, the engine's best move for both sides."""
        while ply < engine_plies:
            key = pos_key(board)
            if key in nodes:
                return
            analysis = engine.analyse(board, depth=depth)
            if analysis.best is None:
                return
            move = chess.Move.from_uci(analysis.best.move)
            san = board.san(move)
            after = board.copy(stack=False)
            after.push(move)
            if pos_key(after) in nodes or pos_key(after) == key:
                return  # the engine would go back to a position the book already has: end the line here, no loop
            mover = mover_at(ply)
            node = {"fen": key, "mover": mover, "source": "engine"}
            if mover == side:
                node |= {
                    "ours": san,
                    "check": {"status": "engine_best", "gap_cp": 0, "depth": depth},
                }
            else:
                node |= {"theirs": [{"san": san, "count": 0, "share": None, "source": "engine"}]}
            nodes[key] = node
            board.push_san(san)
            ply += 1

    def walk(board: chess.Board, ply: int) -> None:
        key = pos_key(board)
        if key in seen:
            return
        seen.add(key)
        if ply >= max_plies:
            if engine is not None:
                extend_with_engine(board.copy(stack=False), ply)
            return
        mover = mover_at(ply)
        kids = sorted(edges.get(key, {}).items(), key=lambda k: (-k[1], k[0]))
        here = pos_n.get(key, 0)
        if mover == side:
            chosen = None
            for san, _ in kids:
                if engine is None:
                    chosen = (san, {"status": "unchecked"})
                    break
                ok, gap, _best = _check(engine, board, san, depth)
                if ok:
                    chosen = (
                        san,
                        {
                            "status": "ok" if san == kids[0][0] else "replaced",
                            "gap_cp": gap,
                            "depth": depth,
                        },
                    )
                    break
            if chosen is None:
                if kids:
                    stopped.append(
                        {"fen": key, "reason": f"no_played_move_within_{ENGINE_FLOOR_CP}cp"}
                    )
                elif engine is not None:
                    extend_with_engine(board.copy(stack=False), ply)
                return
            nodes[key] = {
                "fen": key,
                "mover": mover,
                "ours": chosen[0],
                "check": chosen[1],
                "source": "players",
            }
            nxt = board.copy(stack=False)
            nxt.push_san(chosen[0])
            walk(nxt, ply + 1)
            return
        replies = [
            {"san": san, "count": n, "share": n / here}
            for san, n in kids
            if here and n / here >= MIN_SHARE and n >= floor
        ]
        if not replies:
            if engine is not None:
                extend_with_engine(board.copy(stack=False), ply)
            return
        nodes[key] = {"fen": key, "mover": mover, "theirs": replies, "source": "players"}
        for r in replies:
            nxt = board.copy(stack=False)
            nxt.push_san(r["san"])
            walk(nxt, ply + 1)

    walk(chess.Board(), 0)
    body = {"nodes": nodes, "stopped": stopped}
    return {
        "version": VERSION,
        "id": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16],
        "side": side,
        "name": opening.get("name"),
        "games": games,
        "start": pos_key(chess.Board()),
        "max_plies": max_plies,
        "engine_plies": engine_plies,
        "min_share": MIN_SHARE,
        "min_line_share": MIN_LINE_SHARE,
        "min_line_games": MIN_LINE_GAMES,
        "engine_floor_cp": ENGINE_FLOOR_CP,
        "engine": _engine_record(engine, depth),
        **body,
    }


def is_checked(book: dict) -> bool:
    """True when every move of ours was checked by the engine (a book built with --no-engine is not)."""
    return not any(n.get("check", {}).get("status") == "unchecked" for n in book["nodes"].values())


def lines(book: dict) -> list[list[str]]:
    """Every line the book reaches to its end, as lists of SAN moves."""
    out: list[list[str]] = []

    def go(board: chess.Board, path: list[str], on_path: frozenset[str] = frozenset()) -> None:
        here = pos_key(board)
        node = (
            book["nodes"].get(here) if here not in on_path else None
        )  # a position repeating on the path ends the line

        nxt = (
            [node["ours"]]
            if node and "ours" in node
            else [r["san"] for r in node["theirs"]]
            if node
            else []
        )
        if not nxt:
            if path:
                out.append(path)
            return
        for san in nxt:
            b = board.copy(stack=False)
            b.push_san(san)
            go(b, path + [san], on_path | {here})

    go(chess.Board(), [])
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
    ap.add_argument("--engine-plies", type=int, default=ENGINE_MAX_PLIES, help="how far the engine continues a line, in plies")
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
            book = build(data["openings"][key], engine=analyser, depth=a.depth, engine_plies=a.engine_plies)
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
