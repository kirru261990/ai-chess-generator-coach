import chess
import pytest

from app.engine.stockfish import Analysis, Budget, Score
from app.learner import feedback as f

FREE_KNIGHT = "4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1"  # Rd1 can take the loose knight on d5


def analysis(best, cp=None, mate=None, mate_sign=None):
    return Analysis(best, Score(chess.WHITE, cp=cp, mate=mate, mate_sign=mate_sign), (), 12, "Stockfish test",
                    Budget(depth=12))


def judge(fen, uci, best_uci, before, after):
    board = chess.Board(fen)
    return f.judge(board, chess.Move.from_uci(uci), analysis(best_uci, cp=before), analysis("x", cp=after))


def test_the_engines_best_move_is_best():
    r = judge(FREE_KNIGHT, "d1d5", "d1d5", 300, 300)
    assert r["verdict"] == "good" and r["headline"] == "Best move." and r["better_move"] is None
    assert "You took a free piece." in r["right"]


def test_ignoring_a_free_piece_is_named_with_its_square():
    r = judge(FREE_KNIGHT, "e1f1", "d1d5", 300, 100)
    assert r["verdict"] == "mistake" and r["cost_pawns"] == 2.0
    assert "A free knight on d5 was there to take, and you left it." in r["wrong"]
    assert r["better_move"]["text"] == "Rook d1 to d5 (Rxd5)" and r["better_move"]["to"] == "d5"


def test_verdict_bands():
    assert f._verdict(40, 0, 0)[0] == "good"
    assert f._verdict(100, 0, -100)[0] == "slip"
    assert f._verdict(200, 0, -200)[0] == "mistake"
    assert f._verdict(300, 0, -300)[0] == "blunder"


def test_a_small_drop_while_already_winning_is_not_scolded():
    assert f._verdict(250, 900, 700)[0] == "good"
    assert f._verdict(250, 600, 350)[0] == "mistake"


def test_leaving_a_piece_to_be_taken_is_reported_only_when_confirmed():
    fen = "4k3/8/3p4/8/4N3/8/8/4K3 w - - 0 1"  # Nc5 can be taken by the pawn on d6; Nd2 is safe
    board = chess.Board(fen)
    r = f.judge(board, chess.Move.from_uci("e4c5"), analysis("e4d2", cp=0), analysis("x", cp=-300))
    assert "Your knight on c5 can now be taken." in r["wrong"]
    r = f.judge(board, chess.Move.from_uci("e4c5"), analysis("e4d2", cp=0), analysis("x", cp=-10))
    assert r["wrong"] == []  # not confirmed by the engine: no claim


def test_missing_a_forced_mate_is_flagged():
    board = chess.Board(FREE_KNIGHT)
    best = analysis("d1d8", mate=1, mate_sign=1)
    r = f.judge(board, chess.Move.from_uci("e1f1"), best, analysis("x", cp=0))
    assert "There was a forced checkmate, and this move lets it go." in r["wrong"]


def test_evidence_records_engine_budget_and_detector_versions():
    r = judge(FREE_KNIGHT, "d1d5", "d1d5", 300, 300)
    assert r["evidence"]["budget"] == {"depth": 12, "movetime_ms": None}
    assert r["evidence"]["detectors"] == {"hanging_own": "2", "missed_free": "2"}


@pytest.mark.parametrize("played", ["g1f3", "b1c3"])
def test_describe_move_uses_plain_words_first(played):
    text = f.describe_move(chess.Board(), chess.Move.from_uci(played))
    assert text.startswith("Knight ") and text.endswith(")")


def test_no_pawn_cost_is_claimed_when_a_mate_score_is_involved():
    board = chess.Board(FREE_KNIGHT)
    r = f.judge(board, chess.Move.from_uci("e1f1"), analysis("d1d5", cp=-75),
                analysis("x", mate=1, mate_sign=-1))
    assert r["cost_pawns"] is None and r["verdict"] == "blunder"
    assert "This lets the opponent force checkmate." in r["wrong"]
    r = f.judge(board, chess.Move.from_uci("d1d5"), analysis("d1d5", cp=300), analysis("x", cp=300))
    assert r["cost_pawns"] == 0.0


def test_squares_to_mark_on_the_board_come_only_from_confirmed_misses():
    r = judge(FREE_KNIGHT, "e1f1", "d1d5", 300, 100)  # a free knight on d5 ignored, loss confirmed
    assert r["marks"]["missed_free"] == [{"square": "d5", "piece": "n"}] and r["marks"]["own_hanging"] == []
    ok = judge(FREE_KNIGHT, "d1d5", "d1d5", 300, 300)
    assert ok["marks"] == {"own_hanging": [], "missed_free": []}
    unconfirmed = judge(FREE_KNIGHT, "e1f1", "d1d5", 300, 280)  # the engine does not confirm a loss: nothing is marked
    assert unconfirmed["marks"] == {"own_hanging": [], "missed_free": []}


def test_a_piece_left_hanging_is_marked_with_its_square_and_letter():
    board = chess.Board("4k3/8/3p4/8/4N3/8/8/4K3 w - - 0 1")  # Nc5 hangs to the pawn on d6
    r = f.judge(board, chess.Move.from_uci("e4c5"), analysis("e4d2", cp=0), analysis("x", cp=-300))
    assert r["marks"]["own_hanging"] == [{"square": "c5", "piece": "N"}]
