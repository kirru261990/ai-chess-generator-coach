"""PRD v2 §4.2 thresholds and the shared measurements used by the v3 detectors, the CLEAN selector and the sound-move check.

The numbers are the PRD defaults. Step 1c calibrates them on the owner's games; any change is recorded in ADR 0006 and bumps
RULES_VERSION, because it changes which positions exist.

Readings of the PRD recorded in ADR 0006 (decision 7) and implemented here:
- `MIN_PLY` counts half-moves from the start: the move at ply index 8 (White's 5th move) is the first one considered.
- Material is pawn 1, knight/bishop 3, rook 5, queen 9; kings are not counted. A promotion counts as the new piece.
- A refutation's material swing is measured along the engine's top line, at most MAX_REFUTATION_PLIES plies, from the side
  that wins it. If the line stops right after a capture and the losing side can then recapture profitably on that square
  (static exchange), that recapture is subtracted. A gain the winning side would only make after the limit is never added.
- An "equal alternative" to the best move (M2) is a top-3 line within EQUAL_WITHIN_CP of the best line. This number is not in
  the PRD; it is a reading to be confirmed by the owner in Step 1c.
"""

from __future__ import annotations

import chess

from app.detectors.see import capture_net

RULES_VERSION = "1"

MIN_PLY = 8
DECIDED_LIMIT_CP = 600
M1_EVAL_LOSS_CP = 200
M2_EVAL_LOSS_CP = 150
MATERIAL_MIN = 3
MAX_REFUTATION_PLIES = 4
SOUND_MAX_LOSS_CP = 100
CLEAN_MAX_LOSS_CP = 30  # PRD §4.6
EQUAL_WITHIN_CP = 20  # reading, see above
MATE_CP = 1000  # a mate counts as this many centipawns for losses and limits (never shown as a number)

# M3 missed threat (ADR 0011). Its own settings: M1 and M2 and RULES_VERSION are unchanged. A change here bumps
# `missed_threat.VERSION`, and every M3 evidence record carries these values (`m3_thresholds`).
M3_MIN_PLY = 4  # owner, ADR 0011 decision 1: early traps count
M3_MATERIAL_MIN = 2  # owner, ADR 0011 decision 2: a knight lost for a pawn counts
M3_THREAT_MIN_CP = 150  # ADR 0011 decision 3
M3_EVAL_LOSS_CP = 150  # ADR 0011 decision 3
M3_FTL_MIN_SHARE = 0.5  # ADR 0013: the forced-threat loss must be at least this share of the move's loss (and M3_EVAL_LOSS_CP)
M3_LOST_LIMIT_CP = 400  # ADR 0015: below this score for the player the position is already lost, and a missed threat is not the story
M3_MATE_MAX_MOVES = 2  # a mate threat counts when the engine mates in at most this many opponent moves

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def material(board: chess.Board, color: chess.Color) -> int:
    return sum(len(board.pieces(pt, color)) * v for pt, v in PIECE_VALUES.items())


def balance(board: chess.Board, color: chess.Color) -> int:
    """`color`'s material minus the other side's."""
    return material(board, color) - material(board, not color)


def line_score(line, color: chess.Color) -> int:
    """An engine line's score from `color`'s side in centipawns; a mate is +/-MATE_CP."""
    if line.mate is not None:
        white = line.mate_sign if line.mate_sign is not None else (1 if line.mate > 0 else -1)
        value = MATE_CP * white
    else:
        value = max(-MATE_CP, min(MATE_CP, line.cp or 0))
    return value if color == chess.WHITE else -value


def line_swing(board: chess.Board, pv: tuple[str, ...] | list[str], beneficiary: chess.Color,
               max_plies: int = MAX_REFUTATION_PLIES) -> tuple[int, int]:
    """Material `beneficiary` nets along `pv` (at most `max_plies`), and the number of plies used.

    Stops at the first move that is not legal. See the module notes for the recapture adjustment.
    """
    b = board.copy(stack=False)
    start = balance(b, beneficiary)
    last_capture: chess.Square | None = None
    used = 0
    for uci in list(pv)[:max_plies]:
        move = chess.Move.from_uci(uci)
        if move not in b.legal_moves:
            break
        if b.is_capture(move):
            last_capture = move.to_square
        b.push(move)
        used += 1
    gain = balance(b, beneficiary) - start
    if last_capture is not None and b.turn != beneficiary:
        back = max((capture_net(b, m) for m in b.legal_moves if m.to_square == last_capture), default=0)
        gain -= max(0, back)
    return gain, used


def terminal_score(board: chess.Board, color: chess.Color) -> int:
    """Score of a position with no legal moves, from `color`'s side: checkmate or stalemate."""
    if board.is_checkmate():
        return MATE_CP if board.turn != color else -MATE_CP
    return 0


def sans(board: chess.Board, ucis) -> list[str]:
    """SAN for a sequence of UCI moves from `board` (stops at the first illegal move)."""
    b = board.copy(stack=False)
    out = []
    for uci in ucis:
        move = chess.Move.from_uci(uci)
        if move not in b.legal_moves:
            break
        out.append(b.san(move))
        b.push(move)
    return out


def move_ref(board: chess.Board, uci: str) -> dict:
    return {"uci": uci, "san": board.san(chess.Move.from_uci(uci))}


def has_choice(board: chess.Board) -> bool:
    """More than one legal move (PRD §4.5: the original move was not the only legal move)."""
    moves = iter(board.legal_moves)
    return next(moves, None) is not None and next(moves, None) is not None
