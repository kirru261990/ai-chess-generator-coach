"""Opening line drills (ADR 0022): Practice only, always assisted, never evidence. Misses bring a line back sooner."""

import random
from types import SimpleNamespace as NS

import pytest

from app.learner import repdrill as D
from app.learner import repertoire as R


class AnyMove:
    """An analyser that finds every legal move equally good, so every played move passes the engine check."""

    config = NS(version="Stockfish 19", network="nn", multipv=3, id="ec-test")

    def analyse(self, board, depth=None):
        lines = tuple(
            NS(move=m.uci(), pv=(m.uci(),), cp=0, mate=None, mate_sign=None, depth=18)
            for m in board.legal_moves
        )
        return NS(lines=lines, best=lines[0] if lines else None)


def book_of(side, games, lines, **kw):
    return R.build(
        {"name": "Test", "side": side, "games": games, "lines": [[ln, n] for ln, n in lines]},
        engine=AnyMove(),
        engine_plies=0,
        **kw,
    )


# Black repertoire: 1.e4 c6 2.d4 d5 (also 2.Nc3 d5). Theirs: e4, d4/Nc3. Ours: c6, d5.
BOOK = book_of(
    "black",
    100,
    [
        ("e4", 100),
        ("e4 c6", 100),
        ("e4 c6 d4", 60),
        ("e4 c6 Nc3", 30),
        ("e4 c6 d4 d5", 50),
        ("e4 c6 Nc3 d5", 25),
    ],
)
WHITE_BOOK = book_of("white", 10, [("e4", 10), ("e4 e5", 9)])


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "ledger_path", lambda: tmp_path / "drills.sqlite3")
    c = D.connect()
    yield c
    c.close()


def start(conn, book=BOOK, seed=1, learn=False):
    return D.start(conn, "caro_kann", book, rng=random.Random(seed), learn=learn)


def test_a_black_run_starts_after_white_has_played_the_first_move(conn):
    run = start(conn)
    assert run["side"] == "black" and run["history"] == ["e4"] and run["ply"] == 1
    assert run["fen"] == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def test_a_white_run_starts_at_the_first_move_with_nothing_played(conn):
    run = start(conn, WHITE_BOOK)
    assert run["history"] == [] and run["ply"] == 0 and run["side"] == "white"


def test_the_question_leaks_nothing_before_the_answer(conn):
    run = start(conn)
    assert set(run) == {
        "run_id",
        "key",
        "name",
        "side",
        "fen",
        "ply",
        "history",
        "legal",
        "assisted",
        "source",
        "learn",
        "arrow",
    }
    assert run["arrow"] is None and run["learn"] is False
    assert "ours" not in run and "expected" not in str(run)


def test_a_learn_run_shows_the_move_as_an_arrow_so_the_player_knows_where_to_play(conn):
    run = start(conn, learn=True)
    assert run["learn"] is True and run["arrow"] == "c7c6"


def test_the_question_says_whether_the_position_comes_from_players_or_the_engine(conn):
    assert start(conn)["source"] == "players"


def test_the_right_move_is_a_hit_and_the_run_moves_on_past_their_reply(conn):
    run = start(conn)
    got = D.answer(conn, run["run_id"], "c7c6", BOOK)
    assert got["matched"] is True and got["expected_san"] == "c6"
    assert got["next"]["ply"] == 3 and got["next"]["history"][:2] == ["e4", "c6"]


def test_a_wrong_move_does_not_move_the_line_on_and_the_player_tries_again(conn):
    run = start(conn)
    got = D.answer(conn, run["run_id"], "e7e5", BOOK)
    assert (
        got["matched"] is False
        and got["retry"] is True
        and got["next"] is None
        and got["your_san"] == "e5"
    )
    assert (
        got["expected_san"] is None
    )  # a recall run does not name the move after the first wrong try
    assert (
        conn.execute("SELECT ply FROM rep_run WHERE id = ?", (run["run_id"],)).fetchone()["ply"]
        == 1
    )
    again = D.answer(conn, run["run_id"], "c7c6", BOOK)
    assert again["matched"] is True and again["next"]["ply"] == 3


def test_a_recall_run_shows_the_move_after_two_wrong_tries(conn):
    run = start(conn)
    D.answer(conn, run["run_id"], "e7e5", BOOK)
    second = D.answer(conn, run["run_id"], "a7a6", BOOK)
    assert (
        second["attempts"] == 2
        and second["expected_san"] == "c6"
        and second["expected_uci"] == "c7c6"
    )


def test_several_wrong_tries_on_one_position_count_as_one_miss_and_the_late_right_move_is_no_hit(
    conn,
):
    run = start(conn)
    for bad in ("e7e5", "a7a6", "b7b6"):
        D.answer(conn, run["run_id"], bad, BOOK)
    D.answer(conn, run["run_id"], "c7c6", BOOK)
    s = D.stats(conn, "caro_kann", BOOK)
    assert s["misses"] == 1 and s["hits"] == 0


def test_a_right_first_try_in_a_recall_run_counts_as_a_hit(conn):
    run = start(conn)
    D.answer(conn, run["run_id"], "c7c6", BOOK)
    assert D.stats(conn, "caro_kann", BOOK)["hits"] == 1


def test_a_learn_run_names_the_move_after_a_wrong_try_and_counts_neither_hits_nor_misses(conn):
    run = start(conn, learn=True)
    wrong = D.answer(conn, run["run_id"], "e7e5", BOOK)
    assert wrong["retry"] is True and wrong["expected_uci"] == "c7c6"
    D.answer(conn, run["run_id"], "c7c6", BOOK)
    s = D.stats(conn, "caro_kann", BOOK)
    assert s["hits"] == 0 and s["misses"] == 0 and s["nodes_seen"] == 1 and s["nodes_recalled"] == 0


def test_an_illegal_move_is_refused_and_changes_nothing(conn):
    run = start(conn)
    with pytest.raises(D.DrillError) as e:
        D.answer(conn, run["run_id"], "e2e4", BOOK)
    assert e.value.code == "illegal_move"
    assert D.stats(conn, "caro_kann", BOOK)["nodes_seen"] == 0


def test_the_run_finishes_with_a_summary_after_the_last_answer(conn):
    run = start(conn)
    first = D.answer(conn, run["run_id"], "c7c6", BOOK)
    last = D.answer(conn, run["run_id"], "d7d5", BOOK)
    assert last["next"] is None and last["summary"] == {
        "answered": 2,
        "hits": 2,
        "misses": 0,
        "shown": 0,
    }
    assert first["next"] is not None


def test_a_finished_run_cannot_be_answered_again(conn):
    run = start(conn)
    D.answer(conn, run["run_id"], "c7c6", BOOK)
    D.answer(conn, run["run_id"], "d7d5", BOOK)
    with pytest.raises(D.DrillError) as e:
        D.answer(conn, run["run_id"], "d7d5", BOOK)
    assert e.value.code == "run_finished"


def test_misses_and_hits_are_kept_per_position_and_always_assisted(conn):
    run = start(conn)
    D.answer(conn, run["run_id"], "e7e5", BOOK)
    s = D.stats(conn, "caro_kann", BOOK)
    assert s["misses"] == 1 and s["hits"] == 0 and s["assisted_only"] is True


def test_a_run_answered_through_another_openings_route_is_refused(conn):
    run = start(conn)
    with pytest.raises(D.DrillError) as e:
        D.answer(conn, run["run_id"], "c7c6", BOOK, key="italian")
    assert e.value.code == "run_key_mismatch"


def test_a_run_started_before_the_book_was_rebuilt_is_refused_not_crashed(conn):
    run = start(conn)
    rebuilt = book_of(
        "black", 100, [("e4", 100), ("e4 c6", 100), ("e4 c6 d4", 60), ("e4 c6 d4 d5", 50)]
    )
    with pytest.raises(D.DrillError) as e:
        D.answer(conn, run["run_id"], "c7c6", rebuilt)
    assert e.value.code == "book_changed"


def test_a_book_built_without_the_engine_check_is_not_drilled(conn):
    unchecked = R.build(
        {"name": "T", "side": "black", "games": 10, "lines": [["e4", 10], ["e4 c6", 10]]}
    )
    with pytest.raises(D.DrillError) as e:
        D.start(conn, "caro_kann", unchecked, rng=random.Random(1))
    assert e.value.code == "book_unchecked"


def test_a_line_with_a_miss_comes_back_before_an_unseen_one(conn):
    run = start(conn, seed=3)
    played = (
        conn.execute("SELECT line FROM rep_run WHERE id = ?", (run["run_id"],))
        .fetchone()["line"]
        .split()
    )
    D.answer(conn, run["run_id"], "e7e5", BOOK)  # a miss at the shared first position
    assert {tuple(D.pick_line(conn, "caro_kann", BOOK, random.Random(s))) for s in range(10)}.pop()[
        :1
    ] == tuple(played[:1])
    other = next(ln for ln in (["e4", "c6", "d4", "d5"], ["e4", "c6", "Nc3", "d5"]) if ln != played)
    deeper = R.pos_key(R.board_after(other[:3]))
    conn.execute(
        "INSERT INTO rep_node (key, position, hits, misses) VALUES ('caro_kann', ?, 0, 2)",
        (deeper,),
    )
    assert D.pick_line(conn, "caro_kann", BOOK, random.Random(1)) == other


def test_a_position_reached_by_two_move_orders_is_one_ledger_row():
    transposed = book_of(
        "black",
        100,
        [
            ("e4", 60),
            ("e4 c6", 60),
            ("e4 c6 d4", 60),
            ("e4 c6 d4 d5", 60),
            ("d4", 40),
            ("d4 c6", 40),
            ("d4 c6 e4", 40),
            ("d4 c6 e4 d5", 40),
        ],
    )
    lines = R.lines(transposed)
    last_ours = {D._our_positions(transposed, ln)[-1] for ln in lines}
    assert len(lines) == 2 and len(last_ours) == 1


def test_a_book_with_no_lines_cannot_be_started(conn):
    empty = {"side": "black", "nodes": {}, "games": 0, "stopped": [], "id": "x", "engine": None}
    with pytest.raises(D.DrillError) as e:
        D.start(conn, "x", empty, rng=random.Random(1))
    assert e.value.code == "no_lines"


def test_stats_count_lines_positions_and_how_many_have_been_seen(conn):
    s = D.stats(conn, "caro_kann", BOOK)
    assert (
        s["lines"] == 2 and s["nodes_ours"] == 3 and s["nodes_seen"] == 0 and s["nodes_engine"] == 0
    )


def test_an_engine_led_position_is_counted_apart_and_labelled(conn):
    led = R.build(
        {"name": "T", "side": "black", "games": 10, "lines": [["e4", 10], ["e4 c6", 10]]},
        engine=AnyMove(),
        max_plies=2,
        engine_plies=6,
    )
    s = D.stats(conn, "caro_kann", led)
    assert s["nodes_engine"] > 0 and s["nodes_ours"] > s["nodes_engine"]


def test_a_right_move_returns_the_position_after_it_and_after_the_opponents_reply_so_the_screen_can_show_both(
    conn,
):
    run = start(conn)
    got = D.answer(conn, run["run_id"], "c7c6", BOOK)
    assert got["after_fen"].split()[0] == "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR"
    assert len(got["reply_san"]) == 1 and got["reply_san"][0] in ("d4", "Nc3")
    assert got["reply_fen"] == got["next"]["fen"]


def test_a_wrong_move_returns_no_position_to_draw(conn):
    run = start(conn)
    got = D.answer(conn, run["run_id"], "e7e5", BOOK)
    assert "after_fen" not in got and "reply_fen" not in got


def test_the_last_answer_still_returns_where_the_line_ended(conn):
    run = start(conn)
    D.answer(conn, run["run_id"], "c7c6", BOOK)
    last = D.answer(conn, run["run_id"], "d7d5", BOOK)
    assert last["next"] is None and last["reply_fen"] == last["after_fen"]


def test_an_answer_to_a_question_that_was_already_answered_is_refused_not_counted_twice(conn):
    run = start(conn)
    first = D.answer(conn, run["run_id"], "c7c6", BOOK, ply=run["ply"])
    with pytest.raises(D.DrillError) as e:
        D.answer(conn, run["run_id"], "c7c6", BOOK, ply=run["ply"])  # a repeat of the same request
    assert e.value.code == "stale_question"
    assert D.stats(conn, "caro_kann", BOOK)["hits"] == 1
    assert first["next"]["ply"] > run["ply"]


def test_two_requests_answering_the_same_question_at_once_count_once(tmp_path, monkeypatch):
    import threading

    monkeypatch.setattr(D, "ledger_path", lambda: tmp_path / "drills.sqlite3")
    setup = D.connect()
    run = D.start(setup, "caro_kann", BOOK, rng=random.Random(1), learn=False)
    results: list = []

    def go():
        c = D.connect()
        try:
            results.append(D.answer(c, run["run_id"], "c7c6", BOOK, ply=run["ply"])["matched"])
        except D.DrillError as e:
            results.append(e.code)
        finally:
            c.close()

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(map(str, results)) == ["True", "stale_question"]
    assert D.stats(setup, "caro_kann", BOOK)["hits"] == 1
    setup.close()


def test_current_gives_the_open_question_so_a_screen_can_resynchronise_after_a_lost_response(conn):
    run = start(conn)
    D.answer(
        conn, run["run_id"], "c7c6", BOOK, ply=run["ply"]
    )  # the response is lost on its way back
    now = D.current(conn, run["run_id"], BOOK, key="caro_kann")
    assert (
        now["finished"] is False
        and now["question"]["ply"] == 3
        and now["question"]["history"][:2] == ["e4", "c6"]
    )


def test_current_of_a_finished_run_gives_its_summary_and_last_position(conn):
    run = start(conn)
    D.answer(conn, run["run_id"], "c7c6", BOOK, ply=1)
    D.answer(conn, run["run_id"], "d7d5", BOOK, ply=3)
    now = D.current(conn, run["run_id"], BOOK)
    assert now["finished"] is True and now["summary"]["hits"] == 2 and "fen" in now


def test_current_refuses_another_openings_run(conn):
    run = start(conn)
    with pytest.raises(D.DrillError) as e:
        D.current(conn, run["run_id"], BOOK, key="italian")
    assert e.value.code == "run_key_mismatch"


def test_a_long_line_that_has_been_learned_does_not_starve_a_branch_never_seen(conn):
    book = book_of(
        "black",
        100,
        [
            ("e4", 100),
            ("e4 c6", 100),
            ("e4 c6 d4", 60),
            ("e4 c6 d4 d5", 60),
            ("e4 c6 d4 d5 e5", 40),
            ("e4 c6 d4 d5 e5 Bf5", 40),
            ("e4 c6 d4 d5 e5 Bf5 Nf3", 30),
            ("e4 c6 d4 d5 e5 Bf5 Nf3 e6", 30),
            ("e4 c6 Nc3", 30),
            ("e4 c6 Nc3 d5", 30),
        ],
    )
    long_line = next(ln for ln in R.lines(book) if len(ln) > 6)
    for position in D._our_positions(
        book, long_line
    ):  # every position of the long line was learned with the arrow
        conn.execute(
            "INSERT INTO rep_node (key, position, shown) VALUES ('caro_kann', ?, 3)", (position,)
        )
    assert D.pick_line(conn, "caro_kann", book, random.Random(1)) != long_line
    assert D.pick_line(conn, "caro_kann", book, random.Random(1))[:3] == ["e4", "c6", "Nc3"]
