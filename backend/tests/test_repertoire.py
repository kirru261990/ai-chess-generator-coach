"""Repertoire books (ADR 0022): keyed by position; our moves most played and engine-checked; their replies what players really play;
engine-led play where the players' games run out."""

from types import SimpleNamespace as NS

import pytest

from app.learner import repertoire as R


def doc(side, games, lines):
    return {"name": "Test", "side": side, "games": games, "lines": [[ln, n] for ln, n in lines]}


def line(move, cp):
    return NS(move=move, pv=(move,), cp=cp, mate=None, mate_sign=None, depth=18)


def key_after(*moves):
    return R.pos_key(R.board_after(moves))


class Engine:
    """Scripted analyser keyed by `pos_key`. Scores are White's. A position not scripted returns the first legal move."""

    def __init__(self, tops=None):
        self.tops, self.calls = tops or {}, []
        self.config = NS(version="Stockfish 19", network="nn", multipv=3, id="ec-test")

    def analyse(self, board, depth=None):
        key = R.pos_key(board)
        self.calls.append(key)
        lines = self.tops.get(key)
        if lines is None:
            lines = [line(next(iter(board.legal_moves)).uci(), 0)]
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
    assert book["nodes"][book["start"]]["ours"] == "e4"


def test_their_replies_below_the_share_floor_are_left_out():
    book = R.build(CARO)
    replies = {r["san"]: r for r in book["nodes"][key_after("e4", "c6")]["theirs"]}
    assert set(replies) == {"d4", "Nc3"}  # c4 is 4 of 100 games, below the 6% floor
    assert replies["d4"]["count"] == 60 and replies["d4"]["share"] == pytest.approx(0.6)


def test_a_reply_that_is_rare_among_all_games_is_dropped_even_when_common_in_its_branch():
    book = R.build(
        doc("black", 10000, [("e4", 10000), ("e4 c6", 100), ("e4 c6 d4", 90), ("e4 c6 Nc3", 7)])
    )
    assert [r["san"] for r in book["nodes"][key_after("e4", "c6")]["theirs"]] == ["d4"]


def test_lines_stop_at_the_ply_limit_when_there_is_no_engine():
    moves = ["e4", "c6", "d4", "d5", "Nc3", "dxe4"]
    book = R.build(
        doc("black", 100, [(" ".join(moves[:i]), 100) for i in range(1, 7)]), max_plies=4
    )
    assert max(len(ln) for ln in R.lines(book)) == 4 and book["max_plies"] == 4


def test_the_book_records_whose_turn_each_node_is_and_where_it_starts():
    book = R.build(CARO)
    assert book["nodes"][book["start"]]["mover"] == "white"
    node = book["nodes"][key_after("e4")]
    assert node["mover"] == "black" and node["ours"] == "c6" and node["source"] == "players"


def test_a_transposition_is_one_node_whose_answer_counts_both_move_orders():
    # 1.e4 c6 2.d4 and 1.d4 c6 2.e4 reach the same position. By itself the first order prefers Nf6 (40 to 20); with the second
    # order's games added d5 has 55 and Nf6 50, so the one node answers d5.
    d = doc(
        "black",
        100,
        [
            ("e4", 60),
            ("e4 c6", 60),
            ("e4 c6 d4", 60),
            ("e4 c6 d4 d5", 20),
            ("e4 c6 d4 Nf6", 40),
            ("d4", 40),
            ("d4 c6", 40),
            ("d4 c6 e4", 40),
            ("d4 c6 e4 d5", 35),
            ("d4 c6 e4 Nf6", 10),
        ],
    )
    book = R.build(d, max_plies=6)
    here = key_after("e4", "c6", "d4")
    assert here == key_after("d4", "c6", "e4")
    assert book["nodes"][here]["ours"] == "d5"
    assert sum(1 for k in book["nodes"] if k == here) == 1


def test_a_move_that_loses_more_than_the_floor_is_replaced_by_the_next_most_played_one():
    d = doc("black", 150, [("e4", 150), ("e4 c6", 100), ("e4 e5", 50)])
    engine = Engine({key_after("e4"): [line("e7e5", 20), line("c7c6", 140)]})
    book = R.build(d, engine=engine, depth=18, engine_plies=0)
    node = book["nodes"][key_after("e4")]
    assert node["ours"] == "e5" and node["check"]["status"] == "replaced"


def test_a_move_within_the_floor_of_the_best_is_kept_and_its_gap_recorded():
    d = doc("black", 100, [("e4", 100), ("e4 c6", 100)])
    engine = Engine({key_after("e4"): [line("e7e5", 10), line("c7c6", 40)]})
    node = R.build(d, engine=engine, depth=18, engine_plies=0)["nodes"][key_after("e4")]
    assert node["ours"] == "c6" and node["check"] == {"status": "ok", "gap_cp": 30, "depth": 18}


def test_when_no_played_move_passes_the_check_the_line_stops_and_is_reported():
    d = doc("black", 100, [("e4", 100), ("e4 c6", 100)])
    engine = Engine(
        {key_after("e4"): [line("g7g6", -100), line("c7c6", 100)]}
    )  # scores are White's; c6 is 200 cp worse for Black
    book = R.build(d, engine=engine, depth=18, engine_plies=0)
    assert key_after("e4") not in book["nodes"]
    assert book["stopped"] == [{"fen": key_after("e4"), "reason": "no_played_move_within_50cp"}]


def test_without_an_engine_moves_are_marked_unchecked_and_the_book_says_it_is_not_checked():
    book = R.build(CARO)
    assert book["nodes"][key_after("e4")]["check"] == {"status": "unchecked"}
    assert R.is_checked(book) is False and book["engine"] is None


def test_the_book_records_the_engine_and_the_rules_so_a_change_is_a_new_measurement():
    d = doc("black", 100, [("e4", 100), ("e4 c6", 100)])
    book = R.build(
        d, engine=Engine({key_after("e4"): [line("c7c6", 10)]}), depth=18, engine_plies=0
    )
    assert (
        book["version"] == R.VERSION
        and book["min_share"] == R.MIN_SHARE
        and book["games"] == 100
        and book["side"] == "black"
    )
    assert book["engine"] == {
        "version": "Stockfish 19",
        "network": "nn",
        "depth": 18,
        "multipv": 3,
        "config_id": "ec-test",
        "floor_cp": 50,
    }
    assert R.is_checked(book) is True and len(book["id"]) == 16


def test_the_book_id_changes_when_the_book_changes():
    a = R.build(CARO)
    b = R.build(doc("black", 100, [("e4", 100), ("e4 c6", 100)]))
    assert a["id"] != b["id"] and a["id"] == R.build(CARO)["id"]


def test_leaf_lines_list_every_line_the_book_reaches():
    leaves = [" ".join(ln) for ln in R.lines(R.build(CARO))]
    assert "e4 c6 d4 d5" in leaves and "e4 c6 Nc3" in leaves


def test_where_the_players_run_out_the_engine_plays_both_sides_and_the_nodes_say_so():
    d = doc("black", 100, [("e4", 100), ("e4 c6", 100)])
    engine = Engine(
        {
            key_after("e4", "c6"): [line("d2d4", 30)],  # White's best reply
            key_after("e4", "c6", "d4"): [line("d7d5", 25)],  # Black's best
        }
    )
    book = R.build(d, engine=engine, depth=18, max_plies=2, engine_plies=5)
    white = book["nodes"][key_after("e4", "c6")]
    assert white["source"] == "engine" and white["theirs"] == [
        {"san": "d4", "count": 0, "share": None, "source": "engine"}
    ]
    black = book["nodes"][key_after("e4", "c6", "d4")]
    assert (
        black["source"] == "engine"
        and black["ours"] == "d5"
        and black["check"]["status"] == "engine_best"
    )


def test_the_engine_continuation_stops_at_its_ply_limit_and_never_overwrites_a_players_node():
    d = doc("black", 100, [("e4", 100), ("e4 c6", 100)])
    book = R.build(
        d,
        engine=Engine({key_after("e4"): [line("c7c6", 10)]}),
        depth=18,
        max_plies=2,
        engine_plies=4,
    )
    assert max(len(ln) for ln in R.lines(book)) == 4
    assert book["nodes"][key_after("e4")]["source"] == "players"


def test_a_position_with_no_engine_move_ends_the_line():
    d = doc("white", 10, [("e4", 10)])
    engine = Engine({key_after(): [line("e2e4", 20)], key_after("e4"): []})
    book = R.build(d, engine=engine, depth=18, max_plies=1, engine_plies=6)
    assert [" ".join(ln) for ln in R.lines(book)] == ["e4"]


def test_an_engine_that_would_shuffle_back_to_a_known_position_ends_the_line_instead_of_looping():
    d = doc("white", 10, [("Nf3", 10)])
    engine = Engine(
        {
            key_after(): [line("g1f3", 0)],
            key_after("Nf3"): [line("g8f6", 0)],
            key_after("Nf3", "Nf6"): [line("f3g1", 0)],
            key_after("Nf3", "Nf6", "Ng1"): [line("f6g8", 0)],  # back to the start position
        }
    )
    book = R.build(d, engine=engine, depth=18, max_plies=0, engine_plies=10)
    assert [" ".join(ln) for ln in R.lines(book)] == ["Nf3 Nf6 Ng1"]


def test_lines_end_where_a_position_repeats_even_if_a_book_were_to_contain_a_cycle():
    k = key_after
    nodes = {
        k(): {"mover": "white", "ours": "Nf3", "source": "players"},
        k("Nf3"): {
            "mover": "black",
            "theirs": [{"san": "Nf6", "count": 1, "share": 1.0}],
            "source": "players",
        },
        k("Nf3", "Nf6"): {"mover": "white", "ours": "Ng1", "source": "players"},
        k("Nf3", "Nf6", "Ng1"): {
            "mover": "black",
            "theirs": [{"san": "Ng8", "count": 1, "share": 1.0}],
            "source": "players",
        },
    }
    book = {"nodes": nodes, "start": k(), "side": "white"}
    assert [" ".join(ln) for ln in R.lines(book)] == ["Nf3 Nf6 Ng1 Ng8"]
