"""Helpers shared by the eval-set builders: seeded weak self-play and a material count."""

import random
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.detectors.see import VALUES
from app.engine.stockfish import Engine


def balance(board: chess.Board, color: chess.Color) -> int:
    """Material from `color`'s side: own non-king pieces minus the opponent's."""
    total = 0
    for piece in board.piece_map().values():
        if piece.piece_type != chess.KING:
            total += VALUES[piece.piece_type] * (1 if piece.color == color else -1)
    return total


def self_play(engine: Engine, rng: random.Random, max_plies: int = 90):
    """Yield (board_before, move) from a weak, blunder-prone game (random move 25% of the time)."""
    board = chess.Board()
    while not board.is_game_over() and board.ply() < max_plies:
        if rng.random() < 0.25:
            move = rng.choice(list(board.legal_moves))
        else:
            move = chess.Move.from_uci(engine.play(board, 1, movetime_ms=15))
        yield board.copy(), move
        board.push(move)
