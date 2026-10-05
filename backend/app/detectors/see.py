"""Static exchange evaluation: what can a side win by capturing on a square?

Shared by the material detectors. Simulates the capture sequence with the least
valuable attacker each time, so x-ray attackers appear as pieces move off.

Known v1 limits: pins on the capturing pieces, en passant and promotions are
ignored, so results are an upper bound on what the capturing side can win.
"""

import chess

VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,  # a king "capture" into a defended square must never look profitable
}


def see(board: chess.Board, square: chess.Square, side: chess.Color) -> int:
    """Material `side` nets by starting a capture sequence on `square` (0 if none pays)."""
    target = board.piece_at(square)
    if target is None or target.color == side:
        return 0
    b = board.copy(stack=False)
    captured = [VALUES[target.piece_type]]  # value taken at each step
    stm = side
    while True:
        attackers = b.attackers(stm, square)
        if not attackers:
            break
        frm = min(attackers, key=lambda s: VALUES[b.piece_at(s).piece_type])
        piece = b.piece_at(frm)
        b.remove_piece_at(frm)
        b.set_piece_at(square, piece)
        captured.append(VALUES[piece.piece_type])  # this piece is what the other side may take
        stm = not stm
    captured.pop()  # the last piece moved in was never captured
    gain = 0
    for value in reversed(captured):  # each side may stop capturing: gain never goes below 0
        gain = max(0, value - gain)
    return gain


def capture_net(board: chess.Board, move: chess.Move) -> int:
    """Net material the mover gets from this specific capture, after the opponent's best
    recapture sequence. Negative when the capture loses material (queen takes a defended
    rook). Not a capture, or en passant (no piece on the target square): 0.
    """
    victim = board.piece_at(move.to_square)
    if victim is None or not board.is_capture(move):
        return 0
    after = board.copy(stack=False)
    after.push(move)
    return VALUES[victim.piece_type] - see(after, move.to_square, not board.turn)
