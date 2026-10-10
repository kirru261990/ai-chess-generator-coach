"""The hint ladder (Practice): five steps from a nudge to the answer, so the player does as much of the thinking as possible
(spec D4: scan -> concept cue -> piece/square -> consequence -> answer on request).

1. scan        - a fixed habit prompt ("what did their last move do?"); gives nothing away
2. cue         - what KIND of move to look for (a capture, a check, safety...), from rules on the engine's best move
3. piece       - which piece to look at (the square it stands on)
4. consequence - what the move does (takes, checks, saves, attacks...), checked with python-chess and `hanging_own`
5. move        - the best move itself

Facts only: the best move comes from the engine; every cue and consequence is a rule that was checked on the board
(python-chess and the `hanging_own` detector). When no rule applies, the wording stays neutral and claims nothing more
than "not a capture or a check". No LLM. A step is only revealed when asked for; the server never sends a later step early.
"""

from __future__ import annotations

import chess

from app.detectors import hanging_own
from app.learner.feedback import PIECE
from app.learner.threats import mate_threats, threats

VERSION = "2"  # v2: promotion cue, "develop" checked against move history, neutral "quiet" fallback, consequence step
DETECTOR = {"hanging_own": hanging_own.VERSION}
MAX_LEVEL = 5
SCAN = ("Before you move: what did their last move attack? Is anything of mine loose? Is anything of theirs loose? "
        "Any check, capture or threat?")

HOME = {  # where each side's knights and bishops start
    chess.WHITE: {chess.B1: chess.KNIGHT, chess.G1: chess.KNIGHT, chess.C1: chess.BISHOP, chess.F1: chess.BISHOP},
    chess.BLACK: {chess.B8: chess.KNIGHT, chess.G8: chess.KNIGHT, chess.C8: chess.BISHOP, chess.F8: chess.BISHOP},
}


def _unmoved_minor(board: chess.Board, square: chess.Square) -> bool:
    """A knight or bishop still on its starting square that no move of this game has touched."""
    piece = board.piece_at(square)
    if piece is None or HOME[piece.color].get(square) != piece.piece_type:
        return False
    return all(square not in (m.from_square, m.to_square) for m in board.move_stack)


def cue_kind(board: chess.Board, move: chess.Move) -> str:
    """The kind of move the engine's best move is, in the order a beginner should look for them."""
    if board.is_check():
        return "get_out_of_check"
    if board.is_castling(move):
        return "castle"
    if move.promotion:
        return "promote"
    gives_check = board.gives_check(move)
    if board.is_capture(move):
        return "capture"
    if gives_check:
        return "check"
    found = threats(board)
    if found["threats"] or mate_threats(board):
        return "danger"
    piece = board.piece_at(move.from_square)
    if (piece and piece.piece_type == chess.PAWN and board.fullmove_number <= 6
            and chess.square_name(move.to_square) in ("e4", "d4", "e5", "d5", "c4", "c5")):
        return "centre"
    if board.fullmove_number <= 12 and _unmoved_minor(board, move.from_square):
        return "develop"
    return "quiet"


CUES = {
    "get_out_of_check": "You are in check. Find the safest way out.",
    "castle": "Your king would like to be safer. Think about castling.",
    "promote": "One of your pawns can promote. Look at your pawns near the last rank.",
    "capture": "A capture is the best idea here. What can you take, and is it safe to take?",
    "check": "A check is worth looking at in this position.",
    "danger": "Something of yours is under threat. Deal with that before anything else.",
    "centre": "Take space in the centre with a pawn.",
    "develop": "Bring out a knight or bishop that has not moved yet.",
    "quiet": "The best move here is a quiet one: not a capture or a check. Which move makes your position better?",
}


def _name(symbol: str) -> str:
    return PIECE[symbol.lower()]


def consequences(board: chess.Board, move: chess.Move) -> list[str]:
    """What `move` does, as facts checked on the board. Never empty: a move with no checked effect is called quiet."""
    us = board.turn
    them = not us
    victim = board.piece_at(move.to_square)
    is_capture, is_castle, gives_check = board.is_capture(move), board.is_castling(move), board.gives_check(move)
    before_loose = {h.square: h for h in hanging_own.hanging_pieces(board, us)}
    threatened_mate = bool(mate_threats(board))
    after = board.copy()
    after.push(move)

    if after.is_checkmate():
        return ["It is checkmate."]
    facts = []
    if is_castle:
        facts.append(f"It castles: your king goes to {chess.square_name(after.king(us))}.")
    if is_capture:
        facts.append(f"It takes their {_name(victim.symbol()) if victim else 'pawn'}.")  # no victim on the square: en passant
    if move.promotion:
        facts.append(f"Your pawn becomes a {PIECE[chess.piece_symbol(move.promotion)]}.")
    if gives_check:
        facts.append("It gives check.")
    after_loose = {h.square for h in hanging_own.hanging_pieces(after, us)}
    for square, h in before_loose.items():
        moved_away = square == chess.square_name(move.from_square)
        if square not in after_loose and not moved_away:
            facts.append(f"It saves your {_name(h.piece)} on {square}, which could have been taken.")
        elif moved_away and chess.square_name(move.to_square) not in after_loose:
            facts.append(f"It moves your {_name(h.piece)} out of danger.")
    if threatened_mate and not _can_mate(after):
        facts.append("It stops their checkmate threat.")
    attacked = after.attacks(move.to_square)
    for h in hanging_own.hanging_pieces(after, them):
        if chess.parse_square(h.square) in attacked:
            facts.append(f"It attacks their {_name(h.piece)} on {h.square}, which is not safely defended.")
    if not gives_check and mate_threats(after):
        facts.append("It threatens checkmate next move.")
    if not facts:
        facts.append("It is a quiet move: no capture, check or direct threat. The engine rates it the best move here.")
    return facts


def _can_mate(board: chess.Board) -> bool:
    """The side to move has a move that checkmates."""
    for reply in list(board.legal_moves):
        board.push(reply)
        mated = board.is_checkmate()
        board.pop()
        if mated:
            return True
    return False


def ladder(board: chess.Board, best_uci: str | None, level: int) -> dict:
    """Steps 1..level for this position. Later steps are not included. Step 1 needs no engine move (`best_uci` may be None)."""
    level = max(1, min(MAX_LEVEL, level))
    steps = [{"level": 1, "kind": "scan", "text": SCAN}]
    if level >= 2:
        if best_uci is None:
            raise ValueError("steps after the first need the engine's best move")
        move = chess.Move.from_uci(best_uci)
        kind = cue_kind(board, move)
        steps.append({"level": 2, "kind": kind, "text": CUES[kind]})
    if level >= 3:
        piece = board.piece_at(move.from_square)
        name = PIECE[piece.symbol().lower()] if piece else "piece"
        steps.append({"level": 3, "kind": "piece", "text": f"Look at your {name} on {chess.square_name(move.from_square)}.",
                      "from": chess.square_name(move.from_square)})
    if level >= 4:
        steps.append({"level": 4, "kind": "consequence", "text": " ".join(consequences(board, move)),
                      "from": chess.square_name(move.from_square)})
    if level >= 5:
        steps.append({"level": 5, "kind": "move", "text": f"The engine's choice: {board.san(move)}.",
                      "from": chess.square_name(move.from_square), "to": chess.square_name(move.to_square),
                      "uci": best_uci})
    return {"level": level, "max_level": MAX_LEVEL, "steps": steps, "version": VERSION, "detectors": DETECTOR}
