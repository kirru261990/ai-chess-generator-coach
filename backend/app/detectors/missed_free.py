"""`missed_free` v1: was there a free piece to win, and did the user take it? (T12)

The mirror of `hanging_own`. Opportunity (spec C1): the user is to move and the
opponent has a piece they can win by capturing, meaning a legal capture exists and
the exchange nets at least HANGING_MIN_GAIN pawns. Outcomes:

- taken: the played move captures one of those pieces
- missed: it does not, and (when engine evidence is supplied) the engine confirms an
  evaluation loss. This is the only outcome counted against the user.
- uncertain: it looks like a free piece was ignored but the engine does not confirm a
  loss (a stronger move such as mate, or the capture was not really free). Excluded
  from both numerator and denominator by the pattern layer.
- not_applicable: no free piece to win

Requiring a *legal* capture removes pinned capturers that the static exchange
alone would count. Pawns and kings are not counted in v1. `Result.hanging` lists
the opponent pieces that were available to win.
"""

from __future__ import annotations

import chess

from app.detectors.hanging_own import CONFIRM_LOSS_CP, HANGING_MIN_GAIN, Evidence, Hanging, Result
from app.detectors.see import see

DETECTOR = "missed_free"
VERSION = "1"


def free_pieces(board: chess.Board) -> tuple[Hanging, ...]:
    """Opponent pieces the side to move can win by a legal capture."""
    mover = board.turn
    capture_squares = {m.to_square for m in board.legal_moves if board.is_capture(m)}
    found = []
    for square, piece in board.piece_map().items():
        if piece.color == mover or piece.piece_type in (chess.PAWN, chess.KING):
            continue
        if square not in capture_squares:
            continue
        gain = see(board, square, mover)
        if gain >= HANGING_MIN_GAIN:
            found.append(Hanging(chess.square_name(square), piece.symbol(), gain))
    return tuple(found)


def _result(outcome: str, free=(), confirmed=None, notes=()) -> Result:
    return Result(outcome, free, confirmed, DETECTOR, VERSION, notes)


def detect(board: chess.Board, move: chess.Move, evidence: Evidence | None = None) -> Result:
    """Classify `move`, played from `board` (user to move)."""
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    free = free_pieces(board)
    if not free:
        return _result("not_applicable", notes=("no free piece to win",))
    if board.is_capture(move) and chess.square_name(move.to_square) in {h.square for h in free}:
        return _result("taken", free)
    if evidence is None:
        return _result("missed", free)
    if evidence.best_cp - evidence.after_cp >= CONFIRM_LOSS_CP:
        return _result("missed", free, confirmed=True)
    return _result("uncertain", free, confirmed=False,
                   notes=("a free piece was available but the engine does not confirm a loss",))
