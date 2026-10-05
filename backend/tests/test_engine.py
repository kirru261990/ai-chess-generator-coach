import os
import shutil

import chess
import chess.engine
import pytest

from app.engine.stockfish import Budget, Engine, normalise

pytestmark = pytest.mark.skipif(
    not (os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")),
    reason="Stockfish not installed",
)

FAST = Budget(depth=8)


@pytest.fixture(scope="module")
def engine():
    with Engine() as e:
        yield e


def test_records_engine_version_and_budget(engine):
    a = engine.analyse(chess.Board(), FAST)
    assert "Stockfish" in a.engine
    assert a.budget == FAST and a.depth >= 1
    assert a.best_move in {m.uci() for m in chess.Board().legal_moves}


def test_score_is_normalised_to_perspective(engine):
    board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")  # white is up a queen
    white = engine.analyse(board, FAST, chess.WHITE).score
    black = engine.analyse(board, FAST, chess.BLACK).score
    assert white.cp > 500 and black.cp < -500


def test_default_perspective_is_side_to_move(engine):
    board = chess.Board("4k3/8/8/8/8/8/8/3QK3 b - - 0 1")  # black to move, down a queen
    assert engine.analyse(board, FAST).score.cp < -500


def test_mate_is_kept_separate_from_centipawns(engine):
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1")  # Ra8#
    a = engine.analyse(board, FAST)
    assert a.score.is_mate and a.score.mate == 1 and a.score.cp is None
    assert a.best_move == "a1a8"
    # the same position from the mated side: negative mate distance
    assert engine.analyse(board, FAST, chess.BLACK).score.mate == -1


def test_no_legal_moves(engine):
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")  # black is stalemated
    a = engine.analyse(board, FAST)
    assert a.best_move is None


def test_budget_requires_a_limit():
    with pytest.raises(ValueError):
        Budget(depth=None, movetime_ms=None)


def test_normalise_flips_sign_exactly():
    # engine reports from the side to move; normalise must flip it for the other side
    raw = chess.engine.PovScore(chess.engine.Cp(300), chess.WHITE)
    assert normalise(raw, chess.WHITE).cp == 300
    assert normalise(raw, chess.BLACK).cp == -300
    mate = chess.engine.PovScore(chess.engine.Mate(2), chess.WHITE)
    assert normalise(mate, chess.WHITE).mate == 2
    assert normalise(mate, chess.BLACK).mate == -2
