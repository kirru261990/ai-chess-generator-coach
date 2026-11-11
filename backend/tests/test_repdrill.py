"""Opening line drills (ADR 0022): Practice only, always assisted, never evidence. Misses bring a line back sooner."""

import random

import chess
import pytest

from app.learner import repdrill as D

# Black repertoire: 1.e4 c6 2.d4 d5 (also 2.Nc3 d5). Theirs: e4, d4/Nc3. Ours: c6, d5.
BOOK = {
    "side": "black",
    "name": "Caro-Kann Defence",
    "games": 100,
    "version": "1",
    "nodes": {
        "": {"mover": "white", "theirs": [{"san": "e4", "count": 100, "share": 1.0}]},
        "e4": {"mover": "black", "ours": "c6", "check": {"status": "ok"}},
        "e4 c6": {
            "mover": "white",
            "theirs": [
                {"san": "d4", "count": 60, "share": 0.6},
                {"san": "Nc3", "count": 30, "share": 0.3},
            ],
        },
        "e4 c6 d4": {"mover": "black", "ours": "d5", "check": {"status": "ok"}},
        "e4 c6 Nc3": {"mover": "black", "ours": "d5", "check": {"status": "ok"}},
    },
    "stopped": [],
}
WHITE_BOOK = {
    "side": "white",
    "name": "Test",
    "games": 10,
    "version": "1",
    "nodes": {
        "": {"mover": "white", "ours": "e4", "check": {"status": "ok"}},
        "e4": {"mover": "black", "theirs": [{"san": "e5", "count": 9, "share": 0.9}]},
    },
    "stopped": [],
}


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "ledger_path", lambda: tmp_path / "drills.sqlite3")
    c = D.connect()
    yield c
    c.close()


def start(conn, book=BOOK, seed=1):
    return D.start(conn, "caro_kann", book, rng=random.Random(seed))


def test_a_black_run_starts_after_white_has_played_the_first_move(conn):
    run = start(conn)
    assert run["side"] == "black" and run["history"] == ["e4"] and run["ply"] == 1
    assert run["fen"] == chess.Board().fen().replace(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    )


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
    }
    assert "ours" not in run and "expected" not in str(run)  # the expected move is not named


def test_the_right_move_is_a_hit_and_the_run_moves_on_past_their_reply(conn):
    run = start(conn)
    got = D.answer(conn, run["run_id"], "c7c6", BOOK)
    assert got["matched"] is True and got["expected_san"] == "c6"
    assert got["next"]["ply"] == 3 and got["next"]["history"][:3] == [
        "e4",
        "c6",
        got["next"]["history"][2],
    ]


def test_a_wrong_move_is_a_miss_the_right_one_is_shown_and_the_run_goes_on(conn):
    run = start(conn)
    got = D.answer(conn, run["run_id"], "e7e5", BOOK)
    assert got["matched"] is False and got["expected_san"] == "c6" and got["your_san"] == "e5"
    assert got["next"]["history"][:2] == [
        "e4",
        "c6",
    ]  # the book move is played so the line can continue


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
    assert last["next"] is None and last["summary"] == {"answered": 2, "hits": 2, "misses": 0}
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


def test_a_line_with_a_miss_comes_back_before_an_unseen_one(conn):
    run = start(conn, seed=3)
    played = (
        conn.execute("SELECT line FROM rep_run WHERE id = ?", (run["run_id"],))
        .fetchone()["line"]
        .split()
    )
    D.answer(conn, run["run_id"], "e7e5", BOOK)  # a miss at "e4"
    picks = {tuple(D.pick_line(conn, "caro_kann", BOOK, random.Random(s))) for s in range(10)}
    assert len(picks) == 1 and picks.pop()[:1] == tuple(played[:1])
    # the miss was at the shared first position, so both lines carry it; a miss deeper in one line singles that line out
    other = next(ln for ln in ("e4 c6 d4 d5", "e4 c6 Nc3 d5") if ln.split() != played).split()
    conn.execute(
        "INSERT INTO rep_node (key, prefix, hits, misses) VALUES ('caro_kann', ?, 0, 2)",
        (" ".join(other[:3]),),
    )
    assert D.pick_line(conn, "caro_kann", BOOK, random.Random(1)) == other


def test_a_new_run_is_not_started_while_the_book_has_no_lines(conn):
    with pytest.raises(D.DrillError) as e:
        D.start(
            conn,
            "x",
            {"side": "black", "nodes": {}, "games": 0, "stopped": []},
            rng=random.Random(1),
        )
    assert e.value.code == "no_lines"


def test_stats_count_lines_and_how_many_have_been_seen(conn):
    s = D.stats(conn, "caro_kann", BOOK)
    assert s["lines"] == 2 and s["nodes_ours"] == 3 and s["nodes_seen"] == 0
