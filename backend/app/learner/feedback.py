"""Practice feedback (T33): after each move you make in Practice, say what was right or wrong.

Every statement comes from the engine or a detector, never from an LLM (rule 1 and 2):
- the verdict is the engine's evaluation drop between the best move and the move played
- "left a piece to be taken" and "missed a free piece" come from `hanging_own` and `missed_free`, with the engine's
  confirmation (`uncertain` detector results are not mentioned)
- missed or allowed checkmates come from the engine's mate scores
Practice is assisted (rule 4); the endpoint refuses Play games. Facts are versioned (detector versions, engine budget).
"""

from __future__ import annotations

import chess

from app.detectors import hanging_own, missed_free
from app.detectors.hanging_own import Evidence
from app.engine.stockfish import Analysis, Budget
from app.learner.review import cp_equiv

FEEDBACK_BUDGET = Budget(depth=12)
GOOD_WITHIN_CP = 50  # within this of the best move is a good move
OFF_BELOW_CP = 150  # a small slip; from here on it is a mistake
BLUNDER_CP = 300
DECIDED_CP = 700  # a position this lopsided (either way) is "already decided"; small drops are not scolded
PIECE = {"p": "pawn", "n": "knight", "b": "bishop", "r": "rook", "q": "queen", "k": "king"}


def describe_move(board: chess.Board, move: chess.Move) -> str:
    """'Knight g1 to f3 (Nf3)': plain words first, notation second."""
    piece = board.piece_at(move.from_square)
    name = PIECE[piece.symbol().lower()].capitalize() if piece else "Piece"
    return (f"{name} {chess.square_name(move.from_square)} to {chess.square_name(move.to_square)} "
            f"({board.san(move)})")


def _verdict(loss: int, before: int, after: int) -> tuple[str, str]:
    """(verdict, headline). Verdicts: good, slip, mistake, blunder."""
    if loss <= GOOD_WITHIN_CP:
        return "good", "Good move."
    if before >= DECIDED_CP and after >= DECIDED_CP:
        return "good", "Still winning, though there was a stronger way."
    if loss < OFF_BELOW_CP:
        return "slip", "A small slip. It was playable."
    if loss < BLUNDER_CP:
        return "mistake", "That was a mistake."
    return "blunder", "That was a blunder."


def analyse_move(engine, board: chess.Board, move: chess.Move, user: chess.Color) -> tuple[Analysis, Analysis]:
    """Engine analysis of the position before the move and after it, both from the user's side."""
    best = engine.analyse(board, FEEDBACK_BUDGET, perspective=user)
    played = board.copy()
    played.push(move)
    return best, engine.analyse(played, FEEDBACK_BUDGET, perspective=user)


def judge(board: chess.Board, move: chess.Move, best: Analysis, after: Analysis, opening: str | None = None) -> dict:
    """Feedback for `move` played from `board`. `best` is the analysis of `board` and `after` of the position after the
    move, both scored from the mover's side."""
    b = cp_equiv(best.score.cp, best.score.mate, best.score.mate_sign)
    a = cp_equiv(after.score.cp, after.score.mate, after.score.mate_sign)
    loss = max(0, b - a)
    # Mates are clamped to +/-1000 only to rank moves; that number is not an evaluation, so no pawn cost is claimed.
    mate_involved = best.score.mate is not None or after.score.mate is not None
    is_best = best.best_move == move.uci()
    verdict, headline = ("good", "Best move.") if is_best else _verdict(loss, b, a)
    evidence = Evidence(b, a)
    hang = hanging_own.detect(board, move, evidence)
    free = missed_free.detect(board, move, evidence)

    right, wrong = [], []
    # Squares the page can mark on the board (engine-confirmed misses only; piece = FEN letter, so the page can check
    # the piece is still there when it draws the mark).
    marks = {
        "own_hanging": [{"square": h.square, "piece": h.piece} for h in hang.hanging] if hang.outcome == "missed" else [],
        "missed_free": [{"square": h.square, "piece": h.piece} for h in free.hanging] if free.outcome == "missed" else [],
    }
    if is_best:
        right.append("It is the engine's first choice.")
    if free.outcome == "taken":
        right.append("You took a free piece.")
    if hang.outcome == "taken":
        right.append("None of your pieces was left to be taken.")
    if free.outcome == "missed":
        h = free.hanging[0]
        wrong.append(f"A free {PIECE[h.piece.lower()]} on {h.square} was there to take, and you left it.")
    if hang.outcome == "missed":
        h = hang.hanging[0]
        wrong.append(f"Your {PIECE[h.piece.lower()]} on {h.square} can now be taken.")
    if best.score.mate_sign == 1 and after.score.mate_sign != 1:
        wrong.append("There was a forced checkmate, and this move lets it go.")
    if after.score.mate_sign == -1 and best.score.mate_sign != -1:
        wrong.append("This lets the opponent force checkmate.")
    if b <= -DECIDED_CP and loss < OFF_BELOW_CP and not wrong:
        headline = "A hard position, and this was reasonable."

    # How the move is labelled on the board: book > best > good > slip / mistake / blunder.
    if opening and verdict in ("good", "slip"):
        label = "book"
        right.append(f"A known opening move ({opening}).")
        headline = f"Book move: {opening}."
    elif is_best:
        label = "best"
    else:
        label = verdict  # good, slip, mistake or blunder

    better = None
    if not is_best and best.best_move:
        bm = chess.Move.from_uci(best.best_move)
        better = {"uci": best.best_move, "from": chess.square_name(bm.from_square),
                  "to": chess.square_name(bm.to_square), "text": describe_move(board, bm)}
    return {
        "verdict": verdict,
        "headline": headline,
        "cost_pawns": None if mate_involved else round(loss / 100, 1),
        "right": right,
        "wrong": wrong,
        "better_move": better,
        "marks": marks,
        "classification": {"key": label, "opening": opening if label == "book" else None},
        "played": {"uci": move.uci(), "text": describe_move(board, move)},
        "evidence": {
            "engine": best.engine,
            "budget": {"depth": best.budget.depth, "movetime_ms": best.budget.movetime_ms},
            "detectors": {"hanging_own": hanging_own.VERSION, "missed_free": missed_free.VERSION},
        },
    }
