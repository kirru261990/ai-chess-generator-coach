"""Engine lines for the slip round review (ADR 0021 decision 7): what happens after the played move and after the better move.

  uv run python -m app.learner.slipline build      # lines for every first-slip drill (needs Stockfish; reads the evidence cache; resumable)
  uv run python -m app.learner.slipline summary

Each line is the move plus the engine's best continuation, up to PLIES moves in all (three for each side). The lines are computed once and
stored in `data/drills/slip_lines_v1.json` keyed by drill id and engine config, so answering a drill needs no engine. Every move is the
engine's own; nothing is invented (AGENTS rules 1 and 2). No language model.
"""

from __future__ import annotations

import json
import os
import sys

import chess

from app.learner import drillbank

PLIES = 6
POINTS = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def lines_path():
    return drillbank.bank_dir() / "slip_lines_v1.json"


def _line(board: chess.Board, first: str, analyser) -> list[str]:
    after = board.copy(stack=False)
    after.push(chess.Move.from_uci(first))
    if after.is_game_over():
        return [first]
    return [first, *analyser.analyse(after).best.pv[: PLIES - 1]]


def lines_for(drill: dict, analyser) -> dict:
    """The line after the played move and after the first accepted move (empty when the drill has none)."""
    board = chess.Board(drill["fen"])
    better = _line(board, drill["accepted"][0], analyser) if drill["accepted"] else []
    return {"mine": _line(board, drill["played"], analyser), "better": better, "engine_config": analyser.config.id, "plies": PLIES}


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(POINTS.get(p.piece_type, 0) * (1 if p.color == color else -1) for p in board.piece_map().values())


def steps(fen: str, ucis: list[str]) -> list[dict]:
    """Each move with who plays it (`you` is the side to move in the drill), its SAN, your running material change in points, and the position after it."""
    board = chess.Board(fen)
    me = board.turn
    start, out = _material(board, me), []
    for uci in ucis:
        move = chess.Move.from_uci(uci)
        who, san = ("you" if board.turn == me else "they"), board.san(move)
        board.push(move)
        out.append({"uci": uci, "san": san, "who": who, "points": _material(board, me) - start, "fen": board.fen()})
    return out


def save(lines: dict[str, dict]) -> None:
    path = lines_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(lines, sort_keys=True) + "\n")
    os.replace(tmp, path)  # a reader sees the old file or the new one, never half of one


def load(engine_config: str) -> dict[str, dict]:
    """Stored lines made by this engine config; an unreadable or missing file is no lines."""
    p = lines_path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and v.get("engine_config") == engine_config and v.get("plies") == PLIES} if isinstance(raw, dict) else {}


def review(drill: dict, stored: dict) -> dict | None:
    """What the review screen steps through, or None when no lines are stored for this drill."""
    if not stored:
        return None
    return {"start_fen": drill["fen"], "mine": steps(drill["fen"], stored["mine"]), "better": steps(drill["fen"], stored["better"])}


def build_all() -> dict[str, dict]:
    from app.db.schema import connect
    from app.engine.evidence import open_evidence
    from app.learner import slipbank, slipround

    with open_evidence(connect(str(slipbank.cache_path()))) as engine:
        lines = load(engine.config.id)
        todo = [d for d in slipround.read_slips() if d["id"] not in lines]
        for n, d in enumerate(todo, 1):
            lines[d["id"]] = lines_for(d, engine)
            if n % 25 == 0:
                save(lines)  # resumable
                print(n, "of", len(todo), flush=True)
    save(lines)
    return lines


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["build"]:
        build_all()
    elif argv[:1] != ["summary"]:
        print("usage: slipline build | summary", file=sys.stderr)
        return 2
    p = lines_path()
    print(len(json.loads(p.read_text())) if p.exists() else 0, "drills with lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
