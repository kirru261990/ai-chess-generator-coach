"""`hanging_own` v3 = PRD v2 mistake type M1, hanging piece (PRD §4.3, §4.5; ADR 0006).

After the player's move, the opponent wins at least MATERIAL_MIN by capturing one of the player's pieces, within
MAX_REFUTATION_PLIES, along the engine's top line, and the move loses at least M1_EVAL_LOSS_CP against the best move,
at the evidence depth and at the stability depth (depth - 4).

v2 (`hanging_own.py`) is unchanged and still serves the live Practice game; its frozen results are never compared with v3.

Outcomes:
- mistake: every check holds; `evidence` is the PRD §4.7 record
- uncertain: the loss is big enough but a reliability check fails (the top line is not a capture of the player's piece, the
  swing is too small, the loss does not hold at the stability depth, or none of the engine's top moves is sound, so the piece
  was lost anyway; ADR 0006 decision 8). Excluded from both numerator and denominator.
- no_mistake: the loss is below the threshold
- skipped: before MIN_PLY, only one legal move, or the position was already decided

`target_squares` are squares in the position shown to the player (before the move): the square of the piece that is lost, or,
when the player moved that piece into danger, the square it moved from. `lost_piece` says which case it is (`moved` or
`other`), because a piece that is only in danger after the move cannot be "seen" on the board before it; the owner decides in
Step 1c how those are asked.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from app.detectors import prd_rules as R

DETECTOR = "hanging_own"
VERSION = "3"


@dataclass(frozen=True)
class Finding:
    outcome: str  # mistake | uncertain | no_mistake | skipped
    reason: str
    evidence: dict | None = None
    alternatives: tuple[dict, ...] = ()  # sound top engine moves, for MISTAKE positions


def gates(board: chess.Board, ply: int, before) -> str | None:
    """The PRD skips shared by every v3 detector and the CLEAN selector. Returns the reason, or None to continue."""
    if ply < R.MIN_PLY:
        return "before_min_ply"
    if not R.has_choice(board):
        return "only_legal_move"
    if before.best is None or abs(R.line_score(before.best, board.turn)) > R.DECIDED_LIMIT_CP:
        return "decided"
    return None


def detect(board: chess.Board, move: chess.Move, ply: int, analyser) -> Finding:
    """Classify the player's `move` from `board` (player to move). `ply` is the move's half-move index in the game."""
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    mover = board.turn
    before = analyser.analyse(board)
    skip = gates(board, ply, before)
    if skip:
        return Finding("skipped", skip)

    after_board = board.copy(stack=False)
    after_board.push(move)
    after = analyser.analyse(after_board)
    eval_before = R.line_score(before.best, mover)
    eval_after = R.line_score(after.best, mover) if after.best else R.terminal_score(after_board, mover)
    loss = eval_before - eval_after
    if loss < R.M1_EVAL_LOSS_CP:
        return Finding("no_mistake", "loss_below_threshold")

    pv = after.best.pv if after.best else ()
    first = chess.Move.from_uci(pv[0]) if pv else None
    victim = after_board.piece_at(first.to_square) if first else None
    if first is None or not after_board.is_capture(first) or victim is None or victim.color != mover:
        return Finding("uncertain", "top_line_not_a_capture_of_player_piece")
    swing, used = R.line_swing(after_board, pv, not mover)
    if swing < R.MATERIAL_MIN:
        return Finding("uncertain", "material_swing_below_minimum")

    stab_depth = analyser.config.stability.depth
    s_before = analyser.analyse(board, depth=stab_depth)
    s_after = analyser.analyse(after_board, depth=stab_depth)
    stab_loss = R.line_score(s_before.best, mover) - (
        R.line_score(s_after.best, mover) if s_after.best else R.terminal_score(after_board, mover)
    )
    if stab_loss < R.M1_EVAL_LOSS_CP:
        return Finding("uncertain", "loss_not_stable")

    moved = first.to_square == move.to_square
    target = move.from_square if moved else first.to_square
    refutation = list(pv[:used])
    evidence = {
        "mistake_type": "M1",
        "fen": board.fen(),
        "ply": ply,
        "player_move": R.move_ref(board, move.uci()),
        "best_move": R.move_ref(board, before.best.move),
        "target_squares": [chess.square_name(target)],
        "lost_piece": "moved" if moved else "other",
        "lost_piece_square_after": chess.square_name(first.to_square),
        "refutation_line": {"uci": refutation, "san": R.sans(after_board, refutation)},
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
    return confirm(board, evidence, analyser, "mistake")


def confirm(board: chess.Board, evidence: dict, analyser, outcome: str) -> Finding:
    """ADR 0006 decision 8: a MISTAKE needs at least one sound move among the engine's top lines. Otherwise the material
    was lost whatever the player did (it is not this mistake), and a practice position would have no right answer."""
    from app.detectors.sound import verified_alternatives

    alternatives = verified_alternatives(board, evidence, analyser)
    if not alternatives:
        return Finding("uncertain", "no_sound_move")
    return Finding(outcome, "all_checks_hold", evidence, tuple(alternatives))

