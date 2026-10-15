"""CLEAN positions (PRD v2 §4.6 plus ADR 0006 decision 6): positions where "No immediate threat" is the right answer.

A position (before the player's move) is CLEAN when:
- it passes the shared gates (MIN_PLY, more than one legal move, not decided);
- the player's move lost less than CLEAN_MAX_LOSS_CP against the best move, at the evidence config;
- at least one piece (knight, bishop, rook or queen, either side) is attacked, so the answer is not trivially "nothing";
- the player is not in check;
- there is no M1 or M2 opportunity (decision 6): none of the player's pieces can be won for MATERIAL_MIN or more by a legal
  capture (static exchange), the player has no capture netting MATERIAL_MIN or more (static exchange), and the engine's best
  line does not start with a capture that nets MATERIAL_MIN along the line.

Pawns and kings do not count as "attacked pieces" (a reading: an attacked pawn is on nearly every board).
"""

from __future__ import annotations

import chess

from app.detectors import prd_rules as R
from app.detectors.hanging_own_v4 import Finding, gates
from app.detectors.see import capture_net

DETECTOR = "clean"
VERSION = "1"
COUNTED = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)


def attacked_pieces(board: chess.Board) -> list[str]:
    out = []
    for square, piece in board.piece_map().items():
        if piece.piece_type in COUNTED and board.is_attacked_by(not piece.color, square):
            out.append(chess.square_name(square))
    return sorted(out)


def best_capture_net(board: chess.Board, side: chess.Color) -> int:
    """The most `side` can net with one legal capture (static exchange), as if `side` were to move."""
    b = board
    if board.turn != side:
        b = board.copy(stack=False)
        b.turn = side
        b.ep_square = None
    return max((capture_net(b, m) for m in b.legal_moves if b.is_capture(m)), default=0)


def static_reason(board: chess.Board) -> str | None:
    """The engine-free checks, run first because they are cheap. Returns why the position is not CLEAN, or None."""
    if not attacked_pieces(board):
        return "nothing_attacked"
    if best_capture_net(board, board.turn) >= R.MATERIAL_MIN:
        return "player_has_free_capture"
    if board.is_check():
        return "in_check"
    if best_capture_net(board, not board.turn) >= R.MATERIAL_MIN:
        return "player_piece_can_be_won"
    return None


def detect(board: chess.Board, move: chess.Move, ply: int, analyser) -> Finding:
    """Outcome `clean` (with an evidence record), `not_clean` or `skipped`."""
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    if ply < R.MIN_PLY:
        return Finding("skipped", "before_min_ply")
    reason = static_reason(board)
    if reason:
        return Finding("not_clean", reason)
    mover = board.turn
    before = analyser.analyse(board)
    skip = gates(board, ply, before)
    if skip:
        return Finding("skipped", skip)
    first = chess.Move.from_uci(before.best.move)
    if board.is_capture(first) and R.line_swing(board, before.best.pv, mover)[0] >= R.MATERIAL_MIN:
        return Finding("not_clean", "best_line_wins_material")
    after_board = board.copy(stack=False)
    after_board.push(move)
    after = analyser.analyse(after_board)
    eval_before = R.line_score(before.best, mover)
    eval_after = R.line_score(after.best, mover) if after.best else R.terminal_score(after_board, mover)
    loss = eval_before - eval_after
    if loss >= R.CLEAN_MAX_LOSS_CP:
        return Finding("not_clean", "move_not_sound_enough")
    evidence = {
        "kind": "CLEAN",
        "fen": board.fen(),
        "ply": ply,
        "player_move": R.move_ref(board, move.uci()),
        "best_move": R.move_ref(board, before.best.move),
        "attacked_squares": attacked_pieces(board),
        "answer": "no_immediate_threat",
        "eval_before": eval_before,
        "eval_after": eval_after,
        "eval_loss": loss,
        "engine_config_id": analyser.config.id,
        "detector": DETECTOR,
        "detector_version": VERSION,
        "rules_version": R.RULES_VERSION,
    }
    return Finding("clean", "all_checks_hold", evidence)
