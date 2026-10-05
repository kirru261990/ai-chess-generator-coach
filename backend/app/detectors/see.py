"""Static exchange evaluation: what can a side win by capturing on a square?

Shared by the material detectors. Plays out the capture sequence with real legal
moves, taking with the least valuable legal capturer each time. Pinned pieces,
checks that must be answered and kings that may not capture into attack are therefore
handled by the rules of chess rather than approximated, and x-ray attackers appear as
pieces move off.

Known limits: en passant is ignored, the capturing side always promotes to a queen
(the value of the promotion itself is not counted), and each side is assumed to keep
capturing as long as that pays, never to play a different move mid-sequence.
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
    if b.turn != side:  # evaluate as if `side` is to move
        b.turn = side
        b.ep_square = None
    captured = [VALUES[target.piece_type]]  # value taken at each step
    while True:
        captures = [
            m
            for m in b.legal_moves
            if m.to_square == square and b.is_capture(m) and m.promotion in (None, chess.QUEEN)
        ]
        if not captures:
            break
        move = min(captures, key=lambda m: VALUES[b.piece_type_at(m.from_square)])
        b.push(move)
        captured.append(VALUES[b.piece_type_at(square)])  # this piece may be taken next
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
