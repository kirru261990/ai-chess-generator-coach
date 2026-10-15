"""The SQLite store enforces the PRD v2 rules itself (ADR 0006, PRD §5 and §10)."""

import sqlite3

import pytest

from app.db.schema import SCHEMA_VERSION, SchemaError, connect, transaction

NOW = "2026-10-13T00:00:00+00:00"


@pytest.fixture
def db():
    conn = connect(":memory:")
    conn.execute(
        "INSERT INTO engine_config VALUES ('ec-1', 'Stockfish 19', 'nn', 'abc', 18, 3, 64, 1, 'white', ?)",
        (NOW,),
    )
    for gid, pool in (("g-practice", "PRACTICE"), ("g-heldout", "HELDOUT")):
        conn.execute(
            "INSERT INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
            " VALUES (?, 'chesscom', ?, 'white', '600', 0, ?, '')",
            (gid, gid, pool),
        )
    return conn


def add_position(conn, game_id, pool, kind="MISTAKE", mistake_type="M1", ply=10):
    cur = conn.execute(
        "INSERT INTO position (game_id, ply, fen, kind, mistake_type, source_tag, pool, engine_config_id,"
        " detector_version) VALUES (?, ?, 'fen', ?, ?, 'chesscom', ?, 'ec-1', 'v3')",
        (game_id, ply, kind, mistake_type, pool),
    )
    return cur.lastrowid


def in_session(conn, session_id, position_id, ord_=0):
    conn.execute("INSERT INTO practice_session_position (session_id, position_id, ord) VALUES (?, ?, ?)",
                 (session_id, position_id, ord_))


def new_assessment(conn, mistake_type="M1"):
    return conn.execute(
        "INSERT INTO assessment (user, mistake_type, kind, created_at, due_at, status)"
        " VALUES ('owner', ?, 'BASELINE', ?, ?, 'pending')",
        (mistake_type, NOW, NOW),
    ).lastrowid


def allocate(conn, assessment_id, position_id, ord_=0):
    conn.execute(
        "INSERT INTO assessment_position (assessment_id, position_id, ord) VALUES (?, ?, ?)",
        (assessment_id, position_id, ord_),
    )


def test_creates_schema_once_and_records_version(tmp_path):
    path = tmp_path / "store.sqlite3"
    connect(path).close()
    conn = connect(path)  # second open: no error, nothing re-created
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_refuses_a_store_from_a_newer_version(tmp_path):
    path = tmp_path / "store.sqlite3"
    connect(path).execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(SchemaError):
        connect(path)


def test_game_pool_never_changes(db):
    with pytest.raises(sqlite3.IntegrityError, match="never changes pool"):
        db.execute("UPDATE game SET pool = 'HELDOUT' WHERE id = 'g-practice'")
    db.execute("UPDATE game SET pool = 'PRACTICE' WHERE id = 'g-practice'")  # unchanged value is fine


def test_position_takes_its_games_pool(db):
    with pytest.raises(sqlite3.IntegrityError, match="pool of its game"):
        add_position(db, "g-practice", "HELDOUT")
    pid = add_position(db, "g-practice", "PRACTICE")
    with pytest.raises(sqlite3.IntegrityError, match="never changes pool"):
        db.execute("UPDATE position SET pool = 'HELDOUT' WHERE id = ?", (pid,))
    with pytest.raises(sqlite3.IntegrityError, match="never changes pool"):
        db.execute("UPDATE position SET game_id = 'g-heldout' WHERE id = ?", (pid,))


def test_exposure_matches_pool_and_tested_is_final(db):
    practice = add_position(db, "g-practice", "PRACTICE")
    heldout = add_position(db, "g-heldout", "HELDOUT")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE position SET exposure_status = 'TESTED' WHERE id = ?", (practice,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE position SET exposure_status = 'PRACTICED' WHERE id = ?", (heldout,))
    db.execute("UPDATE position SET exposure_status = 'TESTED' WHERE id = ?", (heldout,))
    with pytest.raises(sqlite3.IntegrityError, match="never reused"):
        db.execute("UPDATE position SET exposure_status = 'UNSEEN' WHERE id = ?", (heldout,))


def test_mistake_type_only_on_mistake_positions(db):
    with pytest.raises(sqlite3.IntegrityError):
        add_position(db, "g-practice", "PRACTICE", kind="CLEAN", mistake_type="M1")
    with pytest.raises(sqlite3.IntegrityError):
        add_position(db, "g-practice", "PRACTICE", kind="MISTAKE", mistake_type=None)
    add_position(db, "g-practice", "PRACTICE", kind="CLEAN", mistake_type=None)


def test_practice_never_uses_a_heldout_position(db):
    heldout = add_position(db, "g-heldout", "HELDOUT")
    practice = add_position(db, "g-practice", "PRACTICE", ply=12)
    sid = db.execute(
        "INSERT INTO practice_session (user, mistake_type, status, started_at) VALUES ('owner', 'M1', 'created', ?)",
        (NOW,),
    ).lastrowid
    insert = (
        "INSERT INTO practice_attempt (session_id, position_id, attempt_number, created_at) VALUES (?, ?, 1, ?)"
    )
    in_session(db, sid, practice)
    # a held-out position can be neither in a session (Step 3) nor have an attempt (PRD 5.3): both rules refuse it
    with pytest.raises(sqlite3.IntegrityError, match="never uses a held-out|position of its session"):
        db.execute(insert, (sid, heldout, NOW))
    with pytest.raises(sqlite3.IntegrityError, match="practice uses only"):
        in_session(db, sid, heldout, ord_=1)
    attempt = db.execute(insert, (sid, practice, NOW)).lastrowid
    # Review finding (PR 61): an existing attempt could be pointed at a held-out position afterwards.
    with pytest.raises(sqlite3.IntegrityError, match="never uses a held-out"):
        db.execute("UPDATE practice_attempt SET position_id = ? WHERE id = ?", (heldout, attempt))


def test_assessments_only_allocate_unseen_heldout_positions(db):
    heldout = add_position(db, "g-heldout", "HELDOUT")
    practice = add_position(db, "g-practice", "PRACTICE", ply=12)
    excluded = add_position(db, "g-heldout", "HELDOUT", ply=14)
    db.execute("UPDATE position SET excluded_reason = 'hand-checked' WHERE id = ?", (excluded,))
    aid = new_assessment(db)
    with pytest.raises(sqlite3.IntegrityError, match="unseen held-out"):
        allocate(db, aid, practice)
    with pytest.raises(sqlite3.IntegrityError, match="unseen held-out"):
        allocate(db, aid, excluded)
    allocate(db, aid, heldout)
    with pytest.raises(sqlite3.IntegrityError, match="never changed"):
        db.execute("UPDATE assessment_position SET position_id = ? WHERE assessment_id = ?", (practice, aid))


def test_results_only_answer_allocated_positions(db):
    heldout = add_position(db, "g-heldout", "HELDOUT")
    other = add_position(db, "g-heldout", "HELDOUT", ply=12)
    practice = add_position(db, "g-practice", "PRACTICE", ply=12)
    aid = new_assessment(db)
    allocate(db, aid, heldout)
    insert = "INSERT INTO assessment_result (assessment_id, position_id) VALUES (?, ?)"
    for not_allocated in (practice, other):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(insert, (aid, not_allocated))
    result = db.execute(insert, (aid, heldout)).lastrowid
    # Review finding (PR 61): a result could be redirected to a practice position afterwards.
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE assessment_result SET position_id = ? WHERE id = ?", (practice, result))


def test_a_tested_position_is_never_assessed_again(db):
    """Review finding (PR 61): a TESTED position could be answered in a second assessment."""
    heldout = add_position(db, "g-heldout", "HELDOUT")
    first = new_assessment(db)
    allocate(db, first, heldout)
    db.execute("INSERT INTO assessment_result (assessment_id, position_id) VALUES (?, ?)", (first, heldout))
    db.execute("UPDATE assessment SET status = 'submitted' WHERE id = ?", (first,))
    db.execute("UPDATE position SET exposure_status = 'TESTED' WHERE id = ?", (heldout,))
    second = new_assessment(db)
    with pytest.raises(sqlite3.IntegrityError):
        allocate(db, second, heldout)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO assessment_result (assessment_id, position_id) VALUES (?, ?)", (second, heldout))


def test_a_position_is_allocated_to_one_assessment_only(db):
    """A CLEAN position fits both mistake types; two open assessments must not share it."""
    clean = add_position(db, "g-heldout", "HELDOUT", kind="CLEAN", mistake_type=None)
    allocate(db, new_assessment(db, "M1"), clean)
    with pytest.raises(sqlite3.IntegrityError):
        allocate(db, new_assessment(db, "M2"), clean)


def test_clean_positions_are_stored_once(db):
    """Review finding (PR 61): NULL mistake types made the plain UNIQUE constraint let duplicates in."""
    add_position(db, "g-heldout", "HELDOUT", kind="CLEAN", mistake_type=None, ply=30)
    with pytest.raises(sqlite3.IntegrityError):
        add_position(db, "g-heldout", "HELDOUT", kind="CLEAN", mistake_type=None, ply=30)
    add_position(db, "g-heldout", "HELDOUT", kind="MISTAKE", mistake_type="M1", ply=30)  # a different kind is fine


def test_one_open_assessment_per_mistake_type(db):
    insert = (
        "INSERT INTO assessment (user, mistake_type, kind, created_at, due_at, status)"
        " VALUES ('owner', ?, 'BASELINE', ?, ?, ?)"
    )
    first = db.execute(insert, ("M1", NOW, NOW, "pending")).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, ("M1", NOW, NOW, "in_progress"))
    db.execute(insert, ("M2", NOW, NOW, "pending"))  # another type is independent
    db.execute("UPDATE assessment SET status = 'submitted' WHERE id = ?", (first,))
    db.execute(insert, ("M1", NOW, NOW, "pending"))  # allowed once the first is submitted


def test_delayed_assessment_needs_its_session(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO assessment (user, mistake_type, kind, created_at, due_at, status)"
            " VALUES ('owner', 'M1', 'DELAYED', ?, ?, 'pending')",
            (NOW, NOW),
        )


def test_assessment_time_is_capped(db):
    heldout = add_position(db, "g-heldout", "HELDOUT")
    aid = new_assessment(db)
    allocate(db, aid, heldout)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO assessment_result (assessment_id, position_id, elapsed_ms) VALUES (?, ?, 300001)",
            (aid, heldout),
        )


def test_baseline_window_is_frozen(db):
    wid = db.execute(
        "INSERT INTO baseline_window (user, mistake_type, time_control, game_ids_json, frozen_at)"
        " VALUES ('owner', 'M1', '600', '[]', ?)",
        (NOW,),
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="never edited"):
        db.execute("UPDATE baseline_window SET game_ids_json = '[1]' WHERE id = ?", (wid,))
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        db.execute("DELETE FROM baseline_window WHERE id = ?", (wid,))


def test_transaction_is_all_or_nothing(db):
    with pytest.raises(sqlite3.IntegrityError), transaction(db):
        add_position(db, "g-practice", "PRACTICE", ply=20)
        add_position(db, "g-practice", "HELDOUT", ply=21)  # refused: the whole block rolls back
    assert db.execute("SELECT COUNT(*) FROM position WHERE ply IN (20, 21)").fetchone()[0] == 0


# --- migrations (review finding on PR 62: v1 stores from Step 1a must upgrade) -----------------------------------------

def v1_store(path, with_color_column=False):
    """A store exactly as the v1 code left it (optionally the Step 1b development build that had the column)."""
    from app.db import schema

    conn = sqlite3.connect(path, isolation_level=None)
    for statement in schema._split(schema._SCHEMA_V1):
        conn.execute(statement)
    if with_color_column:
        conn.execute("ALTER TABLE game ADD COLUMN user_color TEXT")
    conn.execute("PRAGMA user_version = 1")
    pgn = '[White "Owner"]\n[Black "someone"]\n\n1. e4 *'
    conn.execute(
        "INSERT INTO game (id, source, platform_id, time_control, played_at, pool, pgn) VALUES"
        " ('g-1', 'chesscom', '1', '600', 0, 'PRACTICE', ?), ('g-2', 'chesscom', '2', '600', 0, 'HELDOUT', '1. e4 *')",
        (pgn,),
    )
    conn.close()


@pytest.mark.parametrize("with_color_column", [False, True])
def test_v1_store_upgrades_keeping_data_and_backfilling_colours(tmp_path, monkeypatch, with_color_column):
    monkeypatch.setenv("CHESSCOM_USERNAME", "owner")
    path = tmp_path / "v1.sqlite3"
    v1_store(path, with_color_column)
    conn = connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    colours = dict(conn.execute("SELECT id, user_color FROM game").fetchall())
    assert colours == {"g-1": "white", "g-2": None}  # g-2 has no headers: filled by the next import
    assert conn.execute("SELECT pool FROM game WHERE id = 'g-2'").fetchone()[0] == "HELDOUT"
    with pytest.raises(sqlite3.IntegrityError, match="colour"):
        conn.execute(
            "INSERT INTO game (id, source, platform_id, time_control, played_at, pool, pgn)"
            " VALUES ('g-3', 'chesscom', '3', '600', 0, 'PRACTICE', '')"
        )


def test_import_fills_a_missing_colour_without_touching_the_pool(tmp_path, monkeypatch):
    import json

    from app.learner import pools

    monkeypatch.setenv("CHESSCOM_USERNAME", "owner")
    path = tmp_path / "v1.sqlite3"
    v1_store(path)
    conn = connect(path)
    games = tmp_path / "games.jsonl"
    games.write_text(json.dumps({"source_id": "https://www.chess.com/game/live/2", "user_color": "black",
                                 "time_control": "600", "end_time": 5, "pgn": "1. e4 *"}) + "\n")
    conn.execute("UPDATE game SET id = 'chesscom:2' WHERE id = 'g-2'")
    assert pools.import_games(conn, games, {"600"}) == 0
    row = conn.execute("SELECT user_color, pool FROM game WHERE id = 'chesscom:2'").fetchone()
    assert tuple(row) == ("black", "HELDOUT")


def test_a_new_store_and_an_upgraded_store_have_the_same_tables(tmp_path):
    def shape(conn):
        return sorted(tuple(r) for r in conn.execute("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))

    path = tmp_path / "v1.sqlite3"
    v1_store(path)
    assert shape(connect(path)) == shape(connect(":memory:"))


def test_a_retired_position_is_never_assessed_or_practised(db):
    heldout = add_position(db, "g-heldout", "HELDOUT")
    practice = add_position(db, "g-practice", "PRACTICE", ply=12)
    db.execute("UPDATE position SET retired_at = 'now' WHERE id IN (?, ?)", (heldout, practice))
    with pytest.raises(sqlite3.IntegrityError, match="retired"):
        allocate(db, new_assessment(db), heldout)
    sid = db.execute("INSERT INTO practice_session (user, mistake_type, status, started_at)"
                     " VALUES ('owner', 'M1', 'created', ?)", (NOW,)).lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="retired|position of its session"):
        db.execute("INSERT INTO practice_attempt (session_id, position_id, attempt_number, created_at)"
                   " VALUES (?, ?, 1, ?)", (sid, practice, NOW))
    with pytest.raises(sqlite3.IntegrityError, match="practice uses only"):
        in_session(db, sid, practice)  # and a retired position cannot join a session
    # Review finding (PR 65): an attempt on an active position could be pointed at a retired one afterwards.
    active = add_position(db, "g-practice", "PRACTICE", ply=14)
    in_session(db, sid, active)
    attempt = db.execute("INSERT INTO practice_attempt (session_id, position_id, attempt_number, created_at)"
                         " VALUES (?, ?, 1, ?)", (sid, active, NOW)).lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="retired"):
        db.execute("UPDATE practice_attempt SET position_id = ? WHERE id = ?", (practice, attempt))
