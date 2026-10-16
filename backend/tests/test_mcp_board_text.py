import chess
import pytest

from app.mcp.board_text import piece_list, render_board

START = chess.STARTING_FEN
MID = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


def test_white_side_has_rank_8_on_top_and_file_a_left():
    lines = render_board(START).splitlines()
    assert lines[0].split() == list("abcdefgh")
    assert lines[1].startswith("8 ") and lines[1].endswith(" 8")
    assert lines[1].split()[1:-1] == list("♜♞♝♛♚♝♞♜")
    assert lines[8].split()[1:-1] == list("♖♘♗♕♔♗♘♖")
    assert lines[-1] == lines[0]


def test_black_side_is_turned_round():
    lines = render_board(START, "black").splitlines()
    assert lines[0].split() == list("hgfedcba")
    assert lines[1].startswith("1 ")
    assert lines[1].split()[1:-1] == list("♖♘♗♔♕♗♘♖")
    assert lines[8].startswith("8 ")


def test_marked_squares_are_bracketed_and_others_are_not():
    text = render_board(MID, "white", ["h5", "c4"])
    assert text.count("[") == 2
    assert "[♕]" in text and "[♗]" in text
    assert "[" not in render_board(MID)


def test_mark_on_empty_square_and_both_sides_agree_on_marks():
    for side in ("white", "black"):
        assert "[·]" in render_board(START, side, ["e4"])


def test_cells_have_equal_width_marked_or_not():
    plain = render_board(MID).splitlines()
    marked = render_board(MID, marks=["h5"]).splitlines()
    assert [len(x) for x in plain] == [len(x) for x in marked]


def test_bad_mark_is_an_error_not_a_silent_skip():
    with pytest.raises(ValueError):
        render_board(START, marks=["z9"])


def test_piece_list_in_words():
    assert piece_list(START, "white") == "Ke1, Qd1, Ra1, Rh1, Bc1, Bf1, Nb1, Ng1, pawns a2 b2 c2 d2 e2 f2 g2 h2"
    assert piece_list(MID, "black").startswith("Ke8, Qd8, Ra8, Rh8, Bc8, Bf8, Nc6, Nf6, pawns")
    assert "pawns" not in piece_list("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "white")
