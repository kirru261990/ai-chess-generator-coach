"""Build the labelled position set for the `hanging_own` detector (T11).

Positions come from weak, blunder-prone Stockfish self-play (seeded), so no player
data is involved. Each position is a (FEN before the move, move played) pair.
Labels come from a deep engine search and a material count along the engine's
principal variation. That is independent of the detector's static exchange
check, so the later precision/recall numbers are not circular.

  missed:  after the move the engine's best reply is a capture, the line loses
           >= 2 pawns of material for the mover, AND the evaluation drops >= 100 cp
           versus best play (a non-capturing refutation such as a fork is a different
           pattern, so it is excluded as ambiguous)
  taken:   no material loss >= 2 and evaluation drop < 100 cp
  (positions that fit neither are ambiguous and are excluded, and counted)

Run from the repo root:  cd backend && uv run python ../evals/tools/build_hanging_own_set.py
"""

import json
import random
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.detectors.see import VALUES
from app.engine.stockfish import Budget, Engine
from app.learner.review import cp_equiv

SEED = 20261005
ORACLE = Budget(depth=12)
OUT = ROOT / "evals" / "sets" / "hanging_own_v1"
TARGET = {"missed": 25, "hard_negative": 15, "ordinary": 10}
MAX_GAMES = 200
PER_GAME_CAP = {"missed": 5, "hard_negative": 3, "ordinary": 2}  # spreads positions across many games
PV_PLIES = 6


def label_move(engine: Engine, board: chess.Board, move: chess.Move) -> dict | None:
    mover = board.turn
    best = engine.analyse(board, ORACLE, perspective=mover)
    after = board.copy()
    after.push(move)
    if after.is_game_over():
        return None
    a = engine.analyse(after, ORACLE, perspective=mover)
    base = _bal(after, mover)
    walk, last_even, last = after.copy(), None, base
    for i, u in enumerate(a.pv[:PV_PLIES], 1):
        walk.push_uci(u)
        last = _bal(walk, mover)
        if i % 2 == 0:
            last_even = last
    net = (last_even if last_even is not None else last) - base
    loss = cp_equiv(best.score.cp, best.score.mate) - cp_equiv(a.score.cp, a.score.mate)
    first_is_capture = bool(a.pv) and after.is_capture(chess.Move.from_uci(a.pv[0]))
    if net <= -2 and loss >= 100 and first_is_capture:
        label = "missed"
    elif net > -2 and loss < 100:
        label = "taken"
    else:
        return {"label": None}
    return {"label": label, "net_material": net, "loss_cp": loss, "engine": a.engine}


def _bal(board: chess.Board, color: chess.Color) -> int:
    """Material from `color`'s side: own non-king pieces minus the opponent's."""
    total = 0
    for piece in board.piece_map().values():
        if piece.piece_type != chess.KING:
            total += VALUES[piece.piece_type] * (1 if piece.color == color else -1)
    return total


def category(board: chess.Board, move: chess.Move, label: str) -> str:
    if label == "missed":
        return "missed"
    piece = board.piece_at(move.from_square)
    lands_attacked = board.is_attacked_by(not board.turn, move.to_square)
    hard = piece.piece_type not in (chess.PAWN, chess.KING) and (lands_attacked or board.is_capture(move))
    return "hard_negative" if hard else "ordinary"


def self_play(engine: Engine, rng: random.Random):
    """Yield (board_before, move) for a weak, blunder-prone game."""
    board = chess.Board()
    while not board.is_game_over() and board.ply() < 90:
        if rng.random() < 0.25:
            move = rng.choice(list(board.legal_moves))
        else:
            move = chess.Move.from_uci(engine.play(board, 1, movetime_ms=15))
        yield board.copy(), move
        board.push(move)


def main() -> None:
    rng = random.Random(SEED)
    pools: dict[str, list[dict]] = {k: [] for k in TARGET}
    seen, ambiguous, scanned = set(), 0, 0
    with Engine() as engine:
        for g in range(MAX_GAMES):
            taken_here = {k: 0 for k in TARGET}
            for board, move in self_play(engine, rng):
                if board.ply() < 6 or board.fen() in seen:
                    continue
                seen.add(board.fen())
                if rng.random() > 0.5 and not board.is_capture(move):
                    continue  # sample: labelling every quiet move is slow
                info = label_move(engine, board, move)
                scanned += 1
                if info is None:
                    continue
                if info["label"] is None:
                    ambiguous += 1
                    continue
                cat = category(board, move, info["label"])
                if taken_here[cat] < PER_GAME_CAP[cat] and len(pools[cat]) < TARGET[cat] * 2:
                    taken_here[cat] += 1
                    pools[cat].append({"fen": board.fen(), "move_uci": move.uci(),
                                       "move_san": board.san(move), "side_to_move": "white" if board.turn else "black",
                                       "category": cat, **info})
            print(f"game {g + 1}: " + ", ".join(f"{k}={len(v)}" for k, v in pools.items()), flush=True)
            if all(len(pools[k]) >= TARGET[k] for k in TARGET):
                break
    rows = []
    for k, n in TARGET.items():
        rng.shuffle(pools[k])
        rows += pools[k][:n]
    rows.sort(key=lambda r: (r["category"], r["fen"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "positions.jsonl").open("w") as f:
        for i, r in enumerate(rows, 1):
            f.write(json.dumps({"id": f"ho1-{i:03d}", **r}) + "\n")
    short = {k: TARGET[k] - len(pools[k][:TARGET[k]]) for k in TARGET if len(pools[k]) < TARGET[k]}
    print(json.dumps({"positions": len(rows), "scanned": scanned, "ambiguous_excluded": ambiguous,
                      "shortfall": short}))


if __name__ == "__main__":
    main()
