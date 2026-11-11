"""Repertoire lines (ADR 0022): our moves are the most played and engine-checked; their replies are what players really play."""

from types import SimpleNamespace as NS

import chess
import pytest

from app.learner import repertoire as R


def doc(side, games, lines):
    return {"name": "Test", "side": side, "games": games, "lines": [[l, n] for l, n in lines]}


def line(move, cp):
    return NS(move=move, pv=(move,), cp=cp, mate=None, mate_sign=None, depth=18)


class Engine:
    """Scripted analyser: top lines by FEN prefix of moves played; unknown positions are level (+0) with the played move top."""

    def __init__(self, tops=None, default_cp=0):
        self.tops, self.default_cp, self.calls = tops or {}, default_cp, []

    def analyse(self, board, depth=None):
        replay, path = chess.Board(), []
        for mv in board.move_stack:
            path.append(replay.san(mv))
            replay.push(mv)
        key = " ".join(path)
        self.calls.append(key)
        lines = self.tops.get(key)
        if lines is None:
            move = next(iter(board.legal_moves)).uci()
            lines = [line(move, self.default_cp)]
        return NS(lines=tuple(lines), best=lines[0] if lines else None)


CARO = doc(
    "black",
    100,
    [
        ("e4", 100),
        ("e4 c6", 100),
        ("e4 c6 d4", 60),
        ("e4 c6 Nc3", 30),
        ("e4 c6 c4", 4),
        ("e4 c6 d4 d5", 50),
        ("e4 c6 d4 Nf6", 5),
    ],
)


def test_our_move_is_the_most_played_one_at_our_turn():
    book = R.build(doc("white", 100, [("e4", 70), ("d4", 30), ("e4 c6", 40), ("e4 e5", 30)]))
    assert book["nodes"][""]["ours"] == "e4"


def test_their_replies_below_the_share_floor_are_left_out():
    book = R.build(CARO)
    replies = {r["san"]: r for r in book["nodes"]["e4 c6"]["theirs"]}
    assert set(replies) == {"d4", "Nc3"}  # c4 is 4 of 100 games, below the 6% floor
    assert replies["d4"]["count"] == 60 and replies["d4"]["share"] == pytest.approx(0.6)


def test_a_reply_that_is_rare_among_all_games_is_dropped_even_when_common_in_its_branch():
    book = R.build(
        doc("black", 10000, [("e4", 10000), ("e4 c6", 100), ("e4 c6 d4", 90), ("e4 c6 Nc3", 7)])
    )
    assert [r["san"] for r in book["nodes"]["e4 c6"]["theirs"]] == ["d4"]


def test_lines_stop_at_the_ply_limit():
    moves = ["e4", "c6", "d4", "d5", "Nc3", "dxe4"]
    lines = [(" ".join(moves[:i]), 100) for i in range(1, 7)]
    book = R.build(doc("black", 100, lines), max_plies=4)
    assert max(len(k.split()) if k else 0 for k in book["nodes"]) < 4
    assert book["max_plies"] == 4


def test_the_book_records_whose_turn_each_node_is():
    book = R.build(CARO)
    assert book["nodes"][""]["mover"] == "white" and "theirs" in book["nodes"][""]
    assert book["nodes"]["e4"]["mover"] == "black" and book["nodes"]["e4"]["ours"] == "c6"


def test_a_move_that_loses_more_than_the_floor_is_replaced_by_the_next_most_played_one():
    # Black's choices at "e4": c6 (100 games) is 120 cp worse than e5 (50 games) by the engine, so e5 is used.
    d = doc("black", 150, [("e4", 150), ("e4 c6", 100), ("e4 e5", 50)])
    engine = Engine({"e4": [line("e7e5", 20), line("c7c6", 140)]})
    book = R.build(d, engine=engine, depth=18)
    assert book["nodes"]["e4"]["ours"] == "e5"
    assert book["nodes"]["e4"]["check"]["status"] == "replaced"


def test_a_move_within_the_floor_of_the_best_is_kept_and_its_gap_recorded():
    d = doc("black", 100, [("e4", 100), ("e4 c6", 100)])
    engine = Engine({"e4": [line("e7e5", 10), line("c7c6", 40)]})
    node = R.build(d, engine=engine, depth=18)["nodes"]["e4"]
    assert node["ours"] == "c6" and node["check"] == {"status": "ok", "gap_cp": 30, "depth": 18}


def test_when_no_played_move_passes_the_check_the_line_stops_and_is_reported():
    d = doc("black", 100, [("e4", 100), ("e4 c6", 100)])
    engine = Engine(
        {"e4": [line("g7g6", -100), line("c7c6", 100)]}
    )  # scores are White's; c6 is 200 cp worse for Black
    book = R.build(d, engine=engine, depth=18)
    assert "e4" not in book["nodes"] and book["stopped"] == [
        {"prefix": "e4", "reason": "no_played_move_within_50cp"}
    ]


def test_without_an_engine_moves_are_marked_unchecked_not_ok():
    assert R.build(CARO)["nodes"]["e4"]["check"] == {"status": "unchecked"}


def test_the_book_names_its_version_and_rules_so_a_change_is_a_new_measurement():
    book = R.build(CARO)
    assert (
        book["version"] == R.VERSION
        and book["min_share"] == R.MIN_SHARE
        and book["min_line_share"] == R.MIN_LINE_SHARE
    )
    assert book["games"] == 100 and book["side"] == "black"


def test_leaf_lines_list_every_line_the_book_reaches():
    leaves = R.lines(R.build(CARO))
    assert "e4 c6 d4 d5" in leaves and "e4 c6 Nc3" in leaves
