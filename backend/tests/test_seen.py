"""Seen is a property of the board, not of one detector row (review on PR 64)."""

from app.db.schema import connect
from app.learner import seen


def store():
    conn = connect(":memory:")
    conn.execute("INSERT INTO engine_config VALUES ('ec', 'v', 'n', 's', 18, 3, 64, 1, 'white', 'x')")
    conn.execute("INSERT INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
                 " VALUES ('g', 'chesscom', 'g', 'white', '600', 0, 'PRACTICE', '')")
    ids = {}
    for ply, mtype in ((10, "M1"), (10, "M2"), (12, "M1")):
        ids[(ply, mtype)] = conn.execute(
            "INSERT INTO position (game_id, ply, fen, kind, mistake_type, source_tag, pool, engine_config_id,"
            " detector_version) VALUES ('g', ?, 'f', 'MISTAKE', ?, 'chesscom', 'PRACTICE', 'ec', 'v3')",
            (ply, mtype)).lastrowid
    return conn, ids


def reasons(conn):
    return {(r["ply"], r["mistake_type"]): r["excluded_reason"]
            for r in conn.execute("SELECT ply, mistake_type, excluded_reason FROM position")}


def test_marking_a_row_marks_the_whole_board_only():
    conn, ids = store()
    seen.mark_seen(conn, ids[(10, "M1")], "shown")
    assert reasons(conn) == {(10, "M1"): "shown", (10, "M2"): "shown", (12, "M1"): None}


def test_marking_keeps_an_earlier_reason():
    conn, ids = store()
    seen.mark_seen(conn, ids[(10, "M2")], "first")
    seen.mark_seen(conn, ids[(10, "M1")], "second")
    assert reasons(conn)[(10, "M1")] == "first"


def test_propagate_repairs_rows_marked_one_at_a_time():
    conn, ids = store()
    conn.execute("UPDATE position SET excluded_reason = 'old' WHERE id = ?", (ids[(10, "M1")],))
    unseen = {r[0] for r in conn.execute(f"SELECT id FROM position WHERE {seen.UNSEEN_BOARD}")}
    assert unseen == {ids[(12, "M1")]}  # the sibling already counts as seen in queries
    assert seen.propagate(conn) == 1
    assert reasons(conn) == {(10, "M1"): "old", (10, "M2"): "old", (12, "M1"): None}
    assert seen.propagate(conn) == 0
