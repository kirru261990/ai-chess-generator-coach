import chess
import pytest

from app.detectors.hanging_own import Evidence
from app.detectors.missed_free import detect, free_pieces

FREE_KNIGHT = "4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1"  # Rd1 can take the loose knight on d5


def mv(uci):
    return chess.Move.from_uci(uci)


def test_taking_the_free_piece_is_taken():
    r = detect(chess.Board(FREE_KNIGHT), mv("d1d5"))
    assert r.outcome == "taken" and r.hanging[0].square == "d5" and r.hanging[0].gain == 3
    assert r.detector == "missed_free" and r.version == "1"


def test_ignoring_it_is_missed():
    r = detect(chess.Board(FREE_KNIGHT), mv("e1f1"))
    assert r.outcome == "missed" and r.engine_confirmed is None and r.hanging[0].square == "d5"


def test_a_defended_piece_is_not_free():
    board = chess.Board("4k3/8/4p3/3n4/8/8/8/3RK3 w - - 0 1")  # the knight is defended by a pawn
    assert free_pieces(board) == ()
    assert detect(board, mv("e1f1")).outcome == "not_applicable"


def test_a_pinned_capturer_does_not_count():
    # Re2 is pinned to Ke1 by Re8, so it cannot legally take the knight on a2.
    # The black rook on e8 is defended by Kf8, so taking it is only an even trade.
    board = chess.Board("4rk2/8/8/8/8/8/n3R3/4K3 w - - 0 1")
    assert free_pieces(board) == ()
    assert detect(board, mv("e1f1")).outcome == "not_applicable"


def test_engine_evidence_confirms_or_downgrades_to_uncertain():
    board = chess.Board(FREE_KNIGHT)
    confirmed = detect(board, mv("e1f1"), Evidence(best_cp=300, after_cp=0))
    assert confirmed.outcome == "missed" and confirmed.engine_confirmed is True
    doubtful = detect(board, mv("e1f1"), Evidence(best_cp=300, after_cp=250))
    assert doubtful.outcome == "uncertain" and doubtful.engine_confirmed is False


def test_taking_one_of_several_free_pieces_counts_as_taken():
    board = chess.Board("3r2k1/8/8/8/n7/8/8/R2RK3 w - - 0 1")  # Rxa4 and Rxd8+ are both on
    assert {h.square for h in free_pieces(board)} == {"a4", "d8"}
    assert detect(board, mv("a1a4")).outcome == "taken"
    assert detect(board, mv("e1f1")).outcome == "missed"  # not a capture of either


def test_capturing_a_pawn_does_not_count_as_taking_the_free_piece():
    board = chess.Board("4k3/8/8/p2n4/8/8/8/R2RK3 w - - 0 1")  # free knight on d5, loose pawn on a5
    assert detect(board, mv("a1a5")).outcome == "missed"


def test_no_free_piece_is_not_applicable_and_inputs_are_checked():
    start = chess.Board()
    assert detect(start, mv("e2e4")).outcome == "not_applicable"
    fen = start.fen()
    with pytest.raises(ValueError):
        detect(start, mv("e2e5"))
    assert start.fen() == fen and not start.move_stack
