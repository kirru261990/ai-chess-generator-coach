import chess
import pytest

from app.detectors.hanging_own import Evidence, detect, hanging_pieces
from app.detectors.see import see


def sq(name):
    return chess.parse_square(name)


# ---- static exchange evaluation, all hand-checkable ----

@pytest.mark.parametrize(
    ("fen", "square", "side", "expected"),
    [
        ("4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1", "d5", chess.WHITE, 3),   # free knight
        ("4k3/8/4p3/3n4/8/8/8/3RK3 w - - 0 1", "d5", chess.WHITE, 0),  # rook for knight loses
        ("4k3/8/4p3/3n4/4P3/8/8/4K3 w - - 0 1", "d5", chess.WHITE, 2),  # pawn takes defended knight
        ("3r2k1/8/8/3n4/8/8/3R4/3RK3 w - - 0 1", "d5", chess.WHITE, 3),  # rook battery x-ray
        ("8/8/8/8/8/4Bk2/3P4/4K3 w - - 0 1", "e3", chess.BLACK, 0),   # king cannot take a defended piece
        ("4k3/8/8/3n4/8/8/8/4K3 w - - 0 1", "d5", chess.WHITE, 0),    # nothing attacks it
        ("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "d5", chess.WHITE, 0),      # empty square
    ],
)
def test_see(fen, square, side, expected):
    assert see(chess.Board(fen), sq(square), side) == expected


# ---- detector ----

QUEEN_VS_PAWN = "4k3/8/8/3p4/8/3Q4/8/4K3 w - - 0 1"


def test_moving_into_a_pawn_capture_is_missed():
    r = detect(chess.Board(QUEEN_VS_PAWN), chess.Move.from_uci("d3e4"))
    assert r.outcome == "missed" and r.hanging[0].square == "e4" and r.hanging[0].gain == 9
    assert r.engine_confirmed is None and r.version == "1"


def test_a_safe_move_is_taken():
    assert detect(chess.Board(QUEEN_VS_PAWN), chess.Move.from_uci("d3d2")).outcome == "taken"


def test_saving_an_already_attacked_piece_is_taken_and_ignoring_it_is_missed():
    board = chess.Board("4k3/8/8/3p4/4Q3/8/8/4K3 w - - 0 1")  # the queen is attacked by the pawn
    assert detect(board, chess.Move.from_uci("e4d4")).outcome == "taken"
    assert detect(board, chess.Move.from_uci("e1d1")).outcome == "missed"


def test_no_choice_is_not_applicable():
    assert detect(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1"), chess.Move.from_uci("e1e2")).outcome \
        == "not_applicable"


def test_engine_evidence_confirms_or_downgrades_to_uncertain():
    board, move = chess.Board(QUEEN_VS_PAWN), chess.Move.from_uci("d3e4")
    confirmed = detect(board, move, Evidence(best_cp=900, after_cp=0))
    assert confirmed.outcome == "missed" and confirmed.engine_confirmed is True
    doubtful = detect(board, move, Evidence(best_cp=900, after_cp=850))
    assert doubtful.outcome == "uncertain" and doubtful.engine_confirmed is False


def test_pawns_and_kings_are_not_counted():
    board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
    assert hanging_pieces(board, chess.WHITE) == ()


def test_input_board_is_not_mutated_and_illegal_moves_rejected():
    board = chess.Board(QUEEN_VS_PAWN)
    fen = board.fen()
    detect(board, chess.Move.from_uci("d3e4"))
    assert board.fen() == fen and len(board.move_stack) == 0
    with pytest.raises(ValueError):
        detect(board, chess.Move.from_uci("d3d8"))  # blocked by the pawn on d5
