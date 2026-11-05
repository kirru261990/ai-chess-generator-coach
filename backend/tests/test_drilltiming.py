"""Timing classes (ADR 0017): free right away, wins on the next move, wins within 3 moves. Engine replies are scripted by FEN."""

import chess

from app.engine.evidence import EngineConfig, EvidenceAnalysis, Line
from app.learner import drilltiming as T

CFG = EngineConfig("Stockfish 19", "nn-test.nnue", "sha", depth=18, multipv=3, hash_mb=64, threads=1)
# The real position that started this (dc-12, owner's check): White Nxd5 exd5 Rxe7, the knight was the bishop's only defender.
DC12 = "2r4r/1R2bp2/1NPpp1pk/p2n3p/P2P4/3B3P/5PPB/6K1 w - - 6 30"


class Scripted:
    """The engine's best move by FEN; a position not listed gets the first legal move."""

    config = CFG

    def __init__(self, best):
        self.best = best

    def analyse(self, board, depth=None):
        uci = self.best.get(board.fen())
        move = chess.Move.from_uci(uci) if uci else next(iter(board.legal_moves), None)
        lines = (Line(move.uci(), (move.uci(),), 0, None, None, 18),) if move else ()
        return EvidenceAnalysis(board.fen(), CFG.id, lines)


def fen_after(fen, *ucis):
    b = chess.Board(fen)
    for u in ucis:
        b.push_uci(u)
    return b.fen()


def test_a_knight_the_pawn_can_retake_wins_on_the_next_move_not_right_away():
    best = {fen_after(DC12, "b6d5", "e6d5"): "b7e7"}  # after the retake the rook takes the bishop the knight defended
    assert T.moves_to_win(chess.Board(DC12), "b6d5", Scripted(best)) == 2


def test_a_piece_nobody_can_retake_is_right_away():
    fen = "4k3/8/8/3r4/8/8/8/3QK3 w - - 0 1"  # Qxd5: the rook is undefended and nothing retakes
    assert T.moves_to_win(chess.Board(fen), "d1d5", Scripted({})) == 1


def test_an_even_trade_with_no_follow_up_is_not_a_win():
    b = chess.Board("4k3/8/4p3/3n4/8/2N5/8/4K3 w - - 0 1")  # Nxd5 exd5: knight for knight, nothing more
    assert T.moves_to_win(b, "c3d5", Scripted({})) is None


def test_classes_have_plain_names():
    assert T.CLASSES == {1: "right_away", 2: "next_move", 3: "within_3_moves"}


def test_a_free_piece_is_not_right_away_when_their_reply_wins_material_elsewhere():
    fen = "r3k3/8/8/3r4/8/8/8/R2QK3 w - - 0 1"  # Qxd5 wins a rook, but Rxa1 takes the rook the queen was guarding
    best = {fen_after(fen, "d1d5"): "a8a1"}
    assert T.moves_to_win(chess.Board(fen), "d1d5", Scripted(best)) != 1
