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
    assert r.engine_confirmed is None and r.version == "2"


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


# ---- v2: only legal captures make a piece hanging (found by the GPT review of PR #12) ----

def test_version_is_2():
    assert detect(chess.Board(QUEEN_VS_PAWN), chess.Move.from_uci("d3d2")).version == "2"


def test_a_piece_attacked_only_by_a_pinned_pawn_is_not_hanging():
    # Black pawn c4 attacks Nd3 but is pinned to Kc8 by Rc1, so cxd3 is illegal.
    board = chess.Board("2k5/8/8/8/2p5/3N4/8/2R1K3 b - - 0 1")
    assert not [m for m in board.legal_moves if board.is_capture(m)]
    assert hanging_pieces(board, chess.WHITE) == ()


def test_moving_next_to_a_pinned_pawn_is_safe_but_next_to_a_free_pawn_hangs_the_piece():
    pinned = chess.Board("2k5/8/8/8/2p5/8/3N4/2R1K3 w - - 0 1")  # pawn c4 is pinned by Rc1
    free = chess.Board("6k1/8/8/8/2p5/8/3N4/2R1K3 w - - 0 1")  # same, but the king is elsewhere
    nb3 = chess.Move.from_uci("d2b3")
    assert detect(pinned, nb3).outcome == "not_applicable"  # nothing on the board can hang
    assert detect(free, nb3).outcome == "missed"  # cxb3 wins the knight


def test_a_losing_capture_and_a_pinned_cheap_attacker_on_one_target():
    # Mirror of the missed_free review case: the cheap attacker (pawn e7) is pinned and the
    # only legal capture of Nd6 is Qxd6, which loses the queen to cxd6.
    board = chess.Board("4rk2/8/8/8/2p5/3n4/4P3/3QK3 w - - 0 1").mirror()
    assert board.turn == chess.BLACK
    assert hanging_pieces(board, chess.WHITE) == ()


def test_the_best_legal_capturer_sets_the_gain():
    # Black Nd5 is defended by pawn e6. exd5 wins the knight (the queen backs up the pawn, so
    # ...exd5 Qxd5 is an even trade): net 3. Qxd5 would lose the queen (net -5). The best
    # legal capture sets the gain.
    board = chess.Board("4k3/8/4p3/3n4/4P3/8/8/3QK3 w - - 0 1")
    assert [(h.square, h.gain) for h in hanging_pieces(board, chess.BLACK)] == [("d5", 3)]


def test_hanging_pieces_does_not_depend_on_whose_turn_the_board_says_it_is():
    white_to_move = chess.Board("4k3/8/4p3/3n4/4P3/8/8/3QK3 w - - 0 1")
    black_to_move = chess.Board("4k3/8/4p3/3n4/4P3/8/8/3QK3 b - - 0 1")
    assert hanging_pieces(white_to_move, chess.BLACK) == hanging_pieces(black_to_move, chess.BLACK)
