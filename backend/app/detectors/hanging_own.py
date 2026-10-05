"""`hanging_own` v1: did the user leave one of their own pieces to be won? (T11)

Opportunity (spec C1): a position where the user is to move and the choice
matters, meaning at least one legal move leaves a piece hanging and at least one
does not. Outcomes:

- taken: the played move leaves no piece hanging
- missed: the played move leaves a piece hanging, and (when engine evidence is
  supplied) the engine confirms a real evaluation loss
- uncertain: it looks hanging but the engine does not confirm the loss
  (compensation, a trap, or a pin the static check ignores). Excluded from both
  numerator and denominator by the pattern layer.
- not_applicable: no choice to make (nothing could hang, or every move hangs
  something)

A piece is hanging when the opponent has a *legal* capture of it that itself nets at
least HANGING_MIN_GAIN after the best recaptures. Each legal capture is evaluated on
its own, starting with that capturer, so a pinned attacker never makes a piece
hanging and a capture that loses material for the opponent does not count. Pawns and
kings are not counted, and en passant and promotion gains are ignored.

Changes: v2 (T11 follow-up, found by an external review of missed_free) replaced the
square-based static exchange, which could pick a pinned attacker, with the per-capture
evaluation above. Results can differ from v1, so the version was bumped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess

from app.detectors.see import capture_net

DETECTOR = "hanging_own"
VERSION = "2"  # v2: only legal captures count (pinned attackers no longer create hanging pieces)
HANGING_MIN_GAIN = 2  # net material, in pawns
CONFIRM_LOSS_CP = 100  # engine loss needed to confirm a "missed"


@dataclass(frozen=True)
class Evidence:
    """Engine evaluations from the mover's side, in centipawns (mates clamped)."""

    best_cp: int  # position before the move, best play
    after_cp: int  # position after the played move


@dataclass(frozen=True)
class Hanging:
    square: str
    piece: str
    gain: int


@dataclass(frozen=True)
class Result:
    outcome: str  # taken | missed | uncertain | not_applicable
    hanging: tuple[Hanging, ...] = ()
    engine_confirmed: bool | None = None  # None when no engine evidence was given
    detector: str = DETECTOR
    version: str = VERSION
    notes: tuple[str, ...] = field(default_factory=tuple)


def hanging_pieces(board: chess.Board, owner: chess.Color) -> tuple[Hanging, ...]:
    """`owner`'s pieces the opponent can win by a legal capture, with the best net gain.

    Evaluated as if it were the opponent's move, whoever's turn `board` says it is.
    """
    if board.turn == owner:
        board = board.copy(stack=False)
        board.turn = not owner
        board.ep_square = None
    best: dict[chess.Square, int] = {}
    for move in board.legal_moves:
        victim = board.piece_at(move.to_square)
        if victim is None or victim.color != owner or victim.piece_type in (chess.PAWN, chess.KING):
            continue
        net = capture_net(board, move)
        if net >= HANGING_MIN_GAIN:
            best[move.to_square] = max(best.get(move.to_square, 0), net)
    return tuple(
        Hanging(chess.square_name(sq), board.piece_at(sq).symbol(), net)
        for sq, net in sorted(best.items())
    )


def _hangs_after(board: chess.Board, move: chess.Move) -> tuple[Hanging, ...]:
    mover = board.turn
    board.push(move)
    try:
        return hanging_pieces(board, mover)
    finally:
        board.pop()


def detect(board: chess.Board, move: chess.Move, evidence: Evidence | None = None) -> Result:
    """Classify `move`, played from `board` (user to move)."""
    if move not in board.legal_moves:
        raise ValueError(f"illegal move {move.uci()} in {board.fen()}")
    board = board.copy()  # push/pop on a private copy
    played_hangs = _hangs_after(board, move)

    safe_exists = not played_hangs
    unsafe_exists = bool(played_hangs)
    for other in board.legal_moves:
        if safe_exists and unsafe_exists:
            break
        if _hangs_after(board, other):
            unsafe_exists = True
        else:
            safe_exists = True
    if not (safe_exists and unsafe_exists):
        return Result("not_applicable", notes=("no choice between safe and hanging moves",))

    if not played_hangs:
        return Result("taken")
    if evidence is None:
        return Result("missed", played_hangs)
    if evidence.best_cp - evidence.after_cp >= CONFIRM_LOSS_CP:
        return Result("missed", played_hangs, engine_confirmed=True)
    return Result("uncertain", played_hangs, engine_confirmed=False,
                  notes=("looks hanging but the engine does not confirm a loss",))
