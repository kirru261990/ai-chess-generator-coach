"""`missed_free` v3 = PRD v2 mistake type M2, missed free capture (PRD §4.3, §4.5; ADR 0006).

The player had a capture that nets at least MATERIAL_MIN along its engine line (at most MAX_REFUTATION_PLIES), the best move
or an equal alternative (a top-3 line within EQUAL_WITHIN_CP of the best) is that capture, the player did not play one, and the
move played loses at least M2_EVAL_LOSS_CP against the best, at the evidence depth and at the stability depth.

v2 (`missed_free.py`) is unchanged and still serves the live Practice game.

Outcomes (the real-game rate is missed / (missed + taken), PRD §8):
- missed: every check holds; `evidence` is the PRD §4.7 record
- taken: the player played one of the free captures
- uncertain: a free capture existed but the loss is too small, does not hold at the stability depth, or no top move is sound
  (ADR 0006 decision 8); excluded from both
- not_available: no free capture among the best lines
- skipped: before MIN_PLY, only one legal move, or the position was already decided

`target_squares` are the squares of the opponent's pieces that could be won (in the position shown to the player).
"""

from __future__ import annotations

import chess

from app.detectors import prd_rules as R
from app.detectors.hanging_own_v3 import Finding, confirm, gates

DETECTOR = "missed_free"
VERSION = "3"


def free_captures(board: chess.Board, before) -> list[tuple[object, int, int]]:
    """(line, swing, plies used) for each best-or-equal top line that starts with a capture netting >= MATERIAL_MIN."""
    if before.best is None:
        return []
    mover = board.turn
    best = R.line_score(before.best, mover)
    out = []
    for line in before.lines:
        if best - R.line_score(line, mover) > R.EQUAL_WITHIN_CP:
            continue
        first = chess.Move.from_uci(line.move)
        victim = board.piece_at(first.to_square)
        if not board.is_capture(first) or victim is None or victim.color == mover:
            continue
        swing, used = R.line_swing(board, line.pv, mover)
        if swing >= R.MATERIAL_MIN:
            out.append((line, swing, used))
    return out


def detect(board: chess.Board, move: chess.Move, ply: int, analyser) -> Finding:
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    mover = board.turn
    before = analyser.analyse(board)
    skip = gates(board, ply, before)
    if skip:
        return Finding("skipped", skip)
    free = free_captures(board, before)
    if not free:
        return Finding("not_available", "no_free_capture_in_best_lines")
    if move.uci() in {line.move for line, _, _ in free}:
        return Finding("taken", "played_a_free_capture")

    after_board = board.copy(stack=False)
    after_board.push(move)
    after = analyser.analyse(after_board)
    eval_before = R.line_score(before.best, mover)
    eval_after = R.line_score(after.best, mover) if after.best else R.terminal_score(after_board, mover)
    loss = eval_before - eval_after
    if loss < R.M2_EVAL_LOSS_CP:
        return Finding("uncertain", "loss_below_threshold")

    stab_depth = analyser.config.stability.depth
    s_before = analyser.analyse(board, depth=stab_depth)
    s_after = analyser.analyse(after_board, depth=stab_depth)
    stab_loss = R.line_score(s_before.best, mover) - (
        R.line_score(s_after.best, mover) if s_after.best else R.terminal_score(after_board, mover)
    )
    if stab_loss < R.M2_EVAL_LOSS_CP:
        return Finding("uncertain", "loss_not_stable")

    line, swing, used = max(free, key=lambda f: (f[1], -before.lines.index(f[0])))
    capture_line = list(line.pv[:used])
    targets = sorted({chess.square_name(chess.Move.from_uci(f[0].move).to_square) for f in free})
    evidence = {
        "mistake_type": "M2",
        "fen": board.fen(),
        "ply": ply,
        "player_move": R.move_ref(board, move.uci()),
        "best_move": R.move_ref(board, before.best.move),
        "target_squares": targets,
        "free_captures": [R.move_ref(board, f[0].move) for f in free],
        "refutation_line": {"uci": capture_line, "san": R.sans(board, capture_line)},
        "material_swing": swing,
        "eval_before": eval_before,
        "eval_after": eval_after,
        "eval_loss": loss,
        "eval_loss_stability": stab_loss,
        "engine_config_id": analyser.config.id,
        "stability_config_id": analyser.config.stability.id,
        "detector": DETECTOR,
        "detector_version": VERSION,
        "rules_version": R.RULES_VERSION,
    }
    return confirm(board, evidence, analyser, "missed")
