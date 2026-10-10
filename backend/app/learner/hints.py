"""The hint ladder (Practice): four steps from a nudge to the answer, so the player does as much of the thinking as possible.

1. scan    - a fixed habit prompt ("what did their last move do?"); gives nothing away
2. cue     - what KIND of move to look for (a capture, a check, safety...), from rules on the engine's best move
3. piece   - which piece to look at (the square it stands on)
4. move    - the best move itself

Facts only: the best move comes from the engine, the cue from python-chess rules and the `hanging_own` detector.
No LLM. A step is only revealed when asked for; the server never sends a later step early.
"""

from __future__ import annotations

import chess

from app.learner.feedback import PIECE
from app.learner.threats import mate_threats, threats

VERSION = "1"
MAX_LEVEL = 4
SCAN = ("Before you move: what did their last move attack? Is anything of mine loose? Is anything of theirs loose? "
        "Any check, capture or threat?")


def cue_kind(board: chess.Board, move: chess.Move) -> str:
    """The kind of move the engine's best move is, in the order a beginner should look for them."""
    if board.is_check():
        return "get_out_of_check"
    if board.is_castling(move):
        return "castle"
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
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 12:
        return "develop"
    return "improve"


CUES = {
    "get_out_of_check": "You are in check. Find the safest way out.",
    "castle": "Your king would like to be safer. Think about castling.",
    "capture": "A capture is the best idea here. What can you take, and is it safe to take?",
    "check": "A check is worth looking at in this position.",
    "danger": "Something of yours is under threat. Deal with that before anything else.",
    "centre": "Take space in the centre with a pawn.",
    "develop": "Bring out a piece you have not moved yet (a knight or bishop).",
    "improve": "No tactic is on. Improve your least active piece.",
}


def ladder(board: chess.Board, best_uci: str, level: int) -> dict:
    """Steps 1..level for this position. Later steps are not included."""
    level = max(1, min(MAX_LEVEL, level))
    move = chess.Move.from_uci(best_uci)
    steps = [{"level": 1, "kind": "scan", "text": SCAN}]
    if level >= 2:
        kind = cue_kind(board, move)
        steps.append({"level": 2, "kind": kind, "text": CUES[kind]})
    if level >= 3:
        piece = board.piece_at(move.from_square)
        name = PIECE[piece.symbol().lower()] if piece else "piece"
        steps.append({"level": 3, "kind": "piece", "text": f"Look at your {name} on {chess.square_name(move.from_square)}.",
                      "from": chess.square_name(move.from_square)})
    if level >= 4:
        steps.append({"level": 4, "kind": "move", "text": f"The engine's choice: {board.san(move)}.",
                      "from": chess.square_name(move.from_square), "to": chess.square_name(move.to_square),
                      "uci": best_uci})
    return {"level": level, "max_level": MAX_LEVEL, "steps": steps, "version": VERSION}
