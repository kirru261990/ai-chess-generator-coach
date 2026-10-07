"""Threat warnings (Practice): what the opponent can do to you right now.

Facts only, from rules and the `hanging_own` detector (no engine, no LLM):
- `piece_can_be_taken`: a piece of yours the opponent can win by a legal capture that nets at least
  `HANGING_MIN_GAIN` pawns after the best recaptures (the same definition as `hanging_own` v2)
- `mate_threat`: if you passed, the opponent would have a move that checkmates you
- `in_check`: you are in check

A warning is shown to the user when it is their turn, in Practice (assisted) only.
"""

from __future__ import annotations

import chess

from app.detectors import hanging_own
from app.learner.feedback import PIECE

DETECTOR = {"hanging_own": hanging_own.VERSION}


def mate_threats(board: chess.Board) -> list[str]:
    """SAN of each opponent move that would checkmate the side to move if that side passed. Empty when in check."""
    if board.is_check():
        return []
    passed = board.copy(stack=False)
    passed.push(chess.Move.null())
    out = []
    for move in list(passed.legal_moves):
        san = passed.san(move)
        passed.push(move)
        mated = passed.is_checkmate()
        passed.pop()
        if mated:
            out.append(san)
    return out


def threats(board: chess.Board) -> dict:
    """Threats against the side to move."""
    user = board.turn
    found = []
    for h in hanging_own.hanging_pieces(board, user):
        found.append({
            "kind": "piece_can_be_taken",
            "square": h.square,
            "piece": PIECE[h.piece.lower()],
            "text": f"Your {PIECE[h.piece.lower()]} on {h.square} can be taken and you would lose material.",
        })
    for san in mate_threats(board):
        found.append({"kind": "mate_threat", "move": san,
                      "text": f"Your opponent threatens checkmate with {san}."})
    return {"in_check": board.is_check(), "threats": found, "detectors": DETECTOR}
