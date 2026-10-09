import chess

from app.core import openings
from app.learner import feedback as f
from tests.test_feedback import FREE_KNIGHT, analysis


def play(*sans):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    return b


def test_every_line_in_the_book_is_legal_from_the_start():
    for name, line in openings.LINES:
        board = chess.Board()
        for san in line.split():
            board.push_san(san)  # raises if a move is illegal or ambiguous
        assert len(board.move_stack) >= 6, name


def test_names_are_unique_enough_and_the_book_is_not_empty():
    assert len(openings.LINES) >= 55 and len({n for n, _ in openings.LINES}) >= 50
    assert len(openings.book()) > 500


def test_known_opening_moves_are_book_and_odd_ones_are_not():
    assert openings.book_name(play("e4"), 1) is not None
    assert openings.book_name(play("e4", "e5", "Nf3", "Nc6", "Bb5"), 5) is not None
    assert openings.book_name(play("d4", "d5", "c4", "e6"), 4) is not None
    assert openings.book_name(play("e4", "e5", "Qh5"), 3) is None  # not a mainline
    assert openings.book_name(play("a3"), 1) is None
    assert openings.book_name(play("f3"), 1) is None


def test_transpositions_count_as_book():
    # 1.c4 Nf6 2.d4 e6 3.Nc3 Bb4 4.e3 reaches the same position as the Nimzo-Indian line 1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.e3
    assert openings.book_name(play("c4", "Nf6", "d4", "e6", "Nc3", "Bb4", "e3"), 7) is not None


def test_late_moves_and_the_start_position_are_never_book():
    board = play("e4", "e5", "Nf3", "Nc6", "Bb5", "a6")
    assert openings.book_name(board, 0) is None
    assert openings.book_name(board, openings.MAX_BOOK_PLY + 1) is None


def test_a_book_move_is_labelled_book_but_a_blunder_never_is():
    board = chess.Board(FREE_KNIGHT)
    book = f.judge(board, chess.Move.from_uci("d1d5"), analysis("d1d5", cp=300), analysis("x", cp=300), "Test Opening")
    assert book["classification"] == {"key": "book", "opening": "Test Opening"}
    assert book["headline"] == "Book move: Test Opening."
    bad = f.judge(board, chess.Move.from_uci("e1f1"), analysis("d1d5", cp=300), analysis("x", cp=-100), "Test Opening")
    assert bad["classification"]["key"] == "blunder" and bad["classification"]["opening"] is None


def test_labels_without_a_book_are_best_good_and_the_error_grades():
    board = chess.Board(FREE_KNIGHT)

    def label(move, before, after, best="d1d5"):
        return f.judge(board, chess.Move.from_uci(move), analysis(best, cp=before), analysis("x", cp=after))["classification"]["key"]

    assert label("d1d5", 300, 300) == "best"
    assert label("d1d2", 300, 280) == "good"  # not the first choice but within half a pawn
    assert label("d1d2", 300, 180) == "slip"
    assert label("d1d2", 300, 100) == "mistake"
    assert label("e1f1", 300, -100) == "blunder"


def test_names_are_general_where_openings_overlap_and_specific_where_they_do_not():
    assert openings.book_name(play("e4"), 1) == "King's Pawn Opening"
    assert openings.book_name(play("d4"), 1) == "Queen's Pawn Opening"
    assert openings.book_name(play("e4", "e5", "Nf3", "Nc6", "Bb5"), 5) == "Ruy Lopez"  # shared by two Ruy Lopez lines
    assert openings.book_name(play("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"), 10) == "Sicilian Defense: Najdorf"
    assert openings.book_name(play("e4", "e5", "Nf3", "Nc6"), 4) == "King's Pawn Opening"  # Ruy, Italian, Scotch, Four Knights
