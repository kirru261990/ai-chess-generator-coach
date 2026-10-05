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

Each *legal* capture is evaluated on its own, starting with that capturer, so a
pinned cheap attacker is never used and a capture that loses material (queen takes a
defended rook) is neither an opportunity nor a "taken". Pawns and kings are not
counted, and en passant and promotion gains are ignored. v2: recaptures are legal
too, so a defender pinned to its king no longer protects a piece (found by the
full-repository audit of 5 Oct 2026). `Result.hanging` lists
the opponent pieces that were available to win, with the best net gain.
"""

from __future__ import annotations

import chess

from app.detectors.hanging_own import CONFIRM_LOSS_CP, HANGING_MIN_GAIN, Evidence, Hanging, Result
from app.detectors.see import capture_net

DETECTOR = "missed_free"
VERSION = "2"  # v2: exchanges use legal recaptures (a pinned defender cannot recapture)


def free_pieces(board: chess.Board) -> tuple[Hanging, ...]:
    """Opponent pieces the side to move can win by some legal capture (net gain per capture)."""
    best: dict[chess.Square, int] = {}
    for move in board.legal_moves:
        victim = board.piece_at(move.to_square)
        if victim is None or victim.piece_type in (chess.PAWN, chess.KING):
            continue
        net = capture_net(board, move)
        if net >= HANGING_MIN_GAIN:
            best[move.to_square] = max(best.get(move.to_square, 0), net)
    return tuple(
        Hanging(chess.square_name(sq), board.piece_at(sq).symbol(), net)
        for sq, net in sorted(best.items())
    )


def _result(outcome: str, free=(), confirmed=None, notes=()) -> Result:
    return Result(outcome, free, confirmed, DETECTOR, VERSION, notes)


def detect(board: chess.Board, move: chess.Move, evidence: Evidence | None = None) -> Result:
    """Classify `move`, played from `board` (user to move)."""
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    free = free_pieces(board)
    if not free:
        return _result("not_applicable", notes=("no free piece to win",))
    if capture_net(board, move) >= HANGING_MIN_GAIN and (
        chess.square_name(move.to_square) in {h.square for h in free}
    ):
        return _result("taken", free)  # this capture itself wins material, not just the victim's square
    if evidence is None:
        return _result("missed", free)
    if evidence.best_cp - evidence.after_cp >= CONFIRM_LOSS_CP:
        return _result("missed", free, confirmed=True)
    return _result("uncertain", free, confirmed=False,
                   notes=("a free piece was available but the engine does not confirm a loss",))
