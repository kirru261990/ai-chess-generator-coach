"""When does a missed-free-piece drill actually win material? (ADR 0017, "Timing classes")

A drill's capture can be a plain free piece, or an even trade that only pays off on a later move of yours (a follow-up).
This module says which, by counting YOUR moves until you are ahead by at least MATERIAL_MIN, whatever way they take the piece back:

  right_away       you are ahead right after the capture and their best way of taking it back (move 1)
  next_move        you are ahead after your second move (capture, they retake, your next move wins something)
  within_3_moves   you are ahead after your third move
  unclear          not within 3 moves along the engine's best replies: left out of the drill set

"Ahead" is material only (pawn 1, knight/bishop 3, rook 5, queen 9), counted from the start position, after the engine's best reply
to your last move. Their replies and your follow-ups are the pinned evidence engine's top moves (depth 18, cached).

Run (from backend/):  uv run python -m app.learner.drilltiming classify        # writes data/drills/drillbank_v1.timing.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter

import chess

from app.db.schema import connect
from app.detectors import prd_rules as R
from app.learner import drillbank

CLASSES = {1: "right_away", 2: "next_move", 3: "within_3_moves"}
MAX_MOVES = 3


def _engine_move(board: chess.Board, analyser) -> chess.Move | None:
    if board.is_game_over():
        return None
    best = analyser.analyse(board).best
    return chess.Move.from_uci(best.move) if best else None


def _after(board: chess.Board, retake: chess.Move | None, extra: int, mover: chess.Color, analyser) -> int:
    """Your material balance after `retake` (None: they play the engine's reply) and `extra` more moves of yours, each answered."""
    x = board.copy(stack=False)
    if retake is None:  # no way to take it straight back: they still get their best reply, which may win material elsewhere
        retake = _engine_move(x, analyser)
        if retake is None:
            return R.balance(x, mover)
    x.push(retake)
    for _ in range(extra):
        mine = _engine_move(x, analyser)
        if mine is None:
            break
        x.push(mine)
        theirs = _engine_move(x, analyser)
        if theirs is None:
            break
        x.push(theirs)
    return R.balance(x, mover)


def moves_to_win(board: chess.Board, capture_uci: str, analyser, max_moves: int = MAX_MOVES) -> int | None:
    """How many of your moves (1 = the capture alone) until you are ahead by MATERIAL_MIN, for every way they can take it back."""
    mover = board.turn
    start = R.balance(board, mover)
    after = board.copy(stack=False)
    after.push_uci(capture_uci)
    target = chess.parse_square(capture_uci[2:4])
    retakes = [m for m in after.legal_moves if after.is_capture(m) and m.to_square == target]
    options = retakes or [None]
    for extra in range(max_moves):
        if all(_after(after, o, extra, mover, analyser) - start >= R.MATERIAL_MIN for o in options):
            return extra + 1
    return None


def classify(drill: dict, analyser) -> str:
    n = moves_to_win(chess.Board(drill["fen"]), drill["evidence"]["refutation_line"]["uci"][0], analyser)
    return CLASSES.get(n, "unclear")


def timing_path():
    return drillbank.bank_path().with_suffix(".timing.json")


def read_timing() -> dict[str, str]:
    p = timing_path()
    return json.loads(p.read_text()) if p.exists() else {}


def run() -> dict:
    from app.engine.evidence import open_evidence

    drills = [json.loads(line) for line in drillbank.bank_path().open()]
    done = read_timing()
    with open_evidence(connect(drillbank.cache_path())) as analyser:
        for d in drills:
            if d["type"] == "M2" and d["id"] not in done:
                done[d["id"]] = classify(d, analyser)
                timing_path().write_text(json.dumps(done, indent=1) + "\n")
    return dict(Counter(done.values()))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] != ["classify"]:
        print("usage: drilltiming classify", file=sys.stderr)
        return 2
    print(json.dumps(run(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
