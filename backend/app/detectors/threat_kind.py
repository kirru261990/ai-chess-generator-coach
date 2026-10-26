"""Rules-only helpers for M3 missed threat (ADR 0011): does a threat line still work, what kind it is, where it came from.

No engine and no LLM: everything here replays a given line with python-chess and counts material with `prd_rules`. The labels
(`kind`, `origin`) describe a threat for coaching; they never change a detector outcome.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from app.detectors import prd_rules as R

KINDS = ("mate", "capture", "fork", "discovered", "other")
ORIGINS = ("new", "standing", "unknown")
TARGET_MIN = 3  # a fork or discovered attack must hit a piece worth at least this much (or the king)


@dataclass(frozen=True)
class LineResult:
    wins: bool  # mates, or nets at least M3_MATERIAL_MIN for the beneficiary
    mates: bool
    swing: int  # material netted along the line (prd_rules.line_swing), 0 when the line mates early
    plies: int  # plies replayed before the line stopped (limit, illegal move or mate)


def line_result(board: chess.Board, pv, beneficiary: chess.Color, material_min: int = R.M3_MATERIAL_MIN) -> LineResult:
    """Replay `pv` from `board` (at most MAX_REFUTATION_PLIES, stopping at the first illegal move) for `beneficiary`."""
    b = board.copy(stack=False)
    used = 0
    for uci in list(pv)[: R.MAX_REFUTATION_PLIES]:
        move = chess.Move.from_uci(uci)
        if move not in b.legal_moves:
            break
        b.push(move)
        used += 1
        if b.is_checkmate():
            return LineResult(b.turn != beneficiary, b.turn != beneficiary, 0, used)
    swing, _ = R.line_swing(board, pv, beneficiary)
    return LineResult(swing >= material_min, False, swing, used)


def _targets(board: chess.Board, attacker_sq: chess.Square, victim: chess.Color) -> set[chess.Square]:
    """Squares of `victim`'s king and pieces worth TARGET_MIN or more that the piece on `attacker_sq` attacks."""
    out = set()
    for sq in board.attacks(attacker_sq):
        p = board.piece_at(sq)
        if p is None or p.color != victim:
            continue
        if p.piece_type == chess.KING or R.PIECE_VALUES[p.piece_type] >= TARGET_MIN:
            out.add(sq)
    return out


def kind(passed: chess.Board, pv, mates: bool) -> str:
    """Label the threat whose line `pv` starts from `passed` (the opponent to move after the player passed)."""
    if mates:
        return "mate"
    if not pv:
        return "other"
    move = chess.Move.from_uci(pv[0])
    if move not in passed.legal_moves:
        return "other"
    attacker, victim = passed.turn, not passed.turn
    captured = passed.piece_at(move.to_square)
    if (passed.is_capture(move) and captured is not None and captured.color == victim
            and R.PIECE_VALUES[captured.piece_type] >= TARGET_MIN):
        return "capture"  # a pawn grab is labelled by what it does next (e.g. Nxf7 forking queen and rook)
    before = {sq: _targets(passed, sq, victim) for sq in chess.SquareSet(passed.occupied_co[attacker]) if sq != move.from_square}
    after = passed.copy(stack=False)
    after.push(move)
    if len(_targets(after, move.to_square, victim)) >= 2:
        return "fork"
    for sq, old in before.items():
        if after.piece_at(sq) is not None and after.color_at(sq) == attacker and _targets(after, sq, victim) - old:
            return "discovered"
    return "other"


def origin(previous: chess.Board | None, pv) -> str:
    """`new` when the threat line would not have worked before the opponent's last move, `standing` when it would.

    `previous` is the position before the opponent's last move (the opponent to move), or None when unknown. The line is replayed
    from there as it stands; a first move that was not legal then wins nothing, so the threat is new.
    """
    if previous is None:
        return "unknown"
    return "standing" if line_result(previous, pv, previous.turn).wins else "new"
