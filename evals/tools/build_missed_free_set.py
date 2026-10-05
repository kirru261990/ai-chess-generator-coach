"""Build the labelled position set for the `missed_free` detector (T12).

Positions come from seeded weak self-play (no player data). Labels come from a deep
engine search and a material count along the engine's best line, independent of the
detector's static exchange check.

  opportunity: the engine's best move captures a non-pawn piece and its line gains
               >= 2 pawns of material for the mover
  taken:          opportunity, the player captured a non-pawn piece, and the evaluation
                  drop versus best play is under 100 cp
  missed:         opportunity, the player did not capture a non-pawn piece, and the
                  evaluation drop is >= 100 cp
  not_applicable: no opportunity per the engine, although the mover had a capture of a
                  *defended* non-pawn piece available (a hard negative)
  anything else is ambiguous and excluded (counted in the README)

Run from the repo root:  cd backend && uv run python ../evals/tools/build_missed_free_set.py
"""

import json
import random
from pathlib import Path

import chess
from selfplay import balance, self_play

from app.engine.stockfish import Budget, Engine
from app.learner.review import cp_equiv

ROOT = Path(__file__).resolve().parents[2]
SEED = 20261006
ORACLE = Budget(depth=12)
OUT = ROOT / "evals" / "sets" / "missed_free_v1"
TARGET = {"missed": 25, "taken": 15, "not_applicable": 10}
PER_GAME_CAP = {"missed": 5, "taken": 3, "not_applicable": 2}
MAX_GAMES = 300
PV_PLIES = 6


def captures_nonpawn(board: chess.Board, move: chess.Move) -> bool:
    victim = board.piece_at(move.to_square)
    return board.is_capture(move) and victim is not None and victim.piece_type != chess.PAWN


def has_defended_target(board: chess.Board) -> bool:
    """Mover can capture a non-pawn piece that its owner defends (primitive attack check)."""
    return any(
        captures_nonpawn(board, m) and board.is_attacked_by(not board.turn, m.to_square)
        for m in board.legal_moves
    )


def has_nonpawn_capture(board: chess.Board) -> bool:
    return any(captures_nonpawn(board, m) for m in board.legal_moves)


def label_move(engine: Engine, board: chess.Board, move: chess.Move) -> dict:
    mover = board.turn
    best = engine.analyse(board, ORACLE, perspective=mover)
    walk = board.copy()
    base, last_even, last = balance(board, mover), None, balance(board, mover)
    for i, u in enumerate(best.pv[:PV_PLIES], 1):
        walk.push_uci(u)
        last = balance(walk, mover)
        if i % 2 == 0:
            last_even = last
    net_best = (last_even if last_even is not None else last) - base
    best_move = chess.Move.from_uci(best.pv[0]) if best.pv else None
    opportunity = best_move is not None and captures_nonpawn(board, best_move) and net_best >= 2

    if move == best_move:
        loss = 0
    else:
        after = board.copy()
        after.push(move)
        if after.is_game_over():
            return {"label": None}
        a = engine.analyse(after, ORACLE, perspective=mover)
        loss = cp_equiv(best.score.cp, best.score.mate) - cp_equiv(a.score.cp, a.score.mate)
    played_capture = captures_nonpawn(board, move)

    if opportunity and played_capture and loss < 100:
        label = "taken"
    elif opportunity and not played_capture and loss >= 100:
        label = "missed"
    elif not opportunity and has_defended_target(board):
        label = "not_applicable"
    else:
        return {"label": None}
    return {"label": label, "net_material_best": net_best, "loss_cp": loss, "engine": best.engine}


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
                if not has_nonpawn_capture(board):
                    continue  # cheap pre-filter: a free piece needs a capture to exist
                info = label_move(engine, board, move)
                scanned += 1
                if info["label"] is None:
                    ambiguous += 1
                    continue
                cat = info["label"]
                if taken_here[cat] < PER_GAME_CAP[cat] and len(pools[cat]) < TARGET[cat] * 2:
                    taken_here[cat] += 1
                    pools[cat].append({
                        "fen": board.fen(), "move_uci": move.uci(), "move_san": board.san(move),
                        "side_to_move": "white" if board.turn else "black", **info,
                    })
            print(f"game {g + 1}: " + ", ".join(f"{k}={len(v)}" for k, v in pools.items()), flush=True)
            if all(len(pools[k]) >= TARGET[k] for k in TARGET):
                break
    rows = []
    for k, n in TARGET.items():
        rng.shuffle(pools[k])
        rows += pools[k][:n]
    rows.sort(key=lambda r: (r["label"], r["fen"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "positions.jsonl").open("w") as f:
        for i, r in enumerate(rows, 1):
            f.write(json.dumps({"id": f"mf1-{i:03d}", **r}) + "\n")
    short = {k: TARGET[k] - len(pools[k][:TARGET[k]]) for k in TARGET if len(pools[k]) < TARGET[k]}
    print(json.dumps({"positions": len(rows), "games": g + 1, "scanned": scanned,
                      "ambiguous_excluded": ambiguous, "shortfall": short}))


if __name__ == "__main__":
    main()
