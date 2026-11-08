"""The Maia-3 band check (evals/tools/maia_band_check.py): the parts that decide what it measures. No engine is run."""

import importlib.util
from pathlib import Path

import chess
import chess.engine
import chess.pgn

SCRIPT = Path(__file__).resolve().parents[2] / "evals" / "tools" / "maia_band_check.py"
spec = importlib.util.spec_from_file_location("maia_band_check", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def loss(before, after):
    return max(0, tool.to_score(before) - tool.to_score(after))


def test_a_mate_always_outranks_a_centipawn_lead():
    assert tool.to_score(chess.engine.Mate(2)) > tool.to_score(chess.engine.Cp(1200))
    assert tool.to_score(chess.engine.Mate(-2)) < tool.to_score(chess.engine.Cp(-1200))


def test_giving_up_a_forced_mate_for_a_big_lead_is_a_small_loss_not_zero():
    assert 0 < loss(chess.engine.Mate(2), chess.engine.Cp(1200)) < 200  # python-chess alone would score this as no loss


def test_moving_from_a_big_lead_into_a_mate_is_never_an_error():
    assert loss(chess.engine.Cp(1500), chess.engine.Mate(1)) == 0


def test_a_mate_just_delivered_is_a_win_and_being_checkmated_is_a_loss():
    assert tool.to_score(chess.engine.MateGiven) == tool.MATE
    assert tool.to_score(chess.engine.Mate(0)) == -tool.MATE
    assert tool.to_score(chess.engine.Mate(1)) == tool.MATE
    assert tool.to_score(chess.engine.Mate(-1)) == -tool.MATE


def test_delivering_the_mate_that_was_available_is_no_error():
    assert loss(chess.engine.Mate(1), chess.engine.MateGiven) == 0  # Qg7# from 7k/5Q2/5K2/8/8/8/8/8 w
    assert loss(chess.engine.Cp(1500), chess.engine.MateGiven) == 0


def test_ordinary_scores_pass_through_below_the_clamp():
    assert tool.to_score(chess.engine.Cp(35)) == 35
    assert tool.to_score(chess.engine.Cp(-250)) == -250


def synthetic_pgn(tmp_path: Path) -> Path:
    game = chess.pgn.Game()
    game.headers["WhiteElo"], game.headers["BlackElo"] = "700", "650"
    board, node = game.board(), game
    for _ in range(40):  # first legal move in UCI order: a legal, long, deterministic game
        move = chess.Move.from_uci(min(m.uci() for m in board.legal_moves))
        node = node.add_variation(move)
        board.push(move)
        if board.is_game_over():
            break
    path = tmp_path / "sample.pgn"
    path.write_text(str(game) + "\n\n")
    return path


def test_every_position_keeps_the_moves_that_came_before_it(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "SAMPLE", synthetic_pgn(tmp_path))
    found = tool.positions(1000)
    assert found
    for start, history, real, rating in found:
        board = chess.Board(start)
        for uci in history:
            board.push_uci(uci)
        assert len(board.move_stack) == len(history) >= tool.PLY_RANGE[0]  # the model sees the game, not just the position
        assert chess.Move.from_uci(real) in board.legal_moves
        assert rating in (700, 650)
