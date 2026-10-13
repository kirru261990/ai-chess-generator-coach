"""The SQLite store for PRD v2 (ADR 0006): games, pools, positions, sessions, assessments, engine cache.

One file under `data/` (git-ignored), opened with the standard library's `sqlite3`. The rules that must never
be broken are enforced by the database itself, not only by the code that writes to it (PRD §5, §10):

- a game's pool is set once and never changes; a position's pool equals its game's pool and never changes
- PRACTICED is only possible in the PRACTICE pool, TESTED only in the HELDOUT pool, and TESTED is final
- practice attempts only use PRACTICE positions, assessment results only HELDOUT positions
- at most one unsubmitted assessment per user and mistake type
- a frozen real-game baseline window is never edited or deleted

`connect()` creates the tables on first use. A schema change bumps SCHEMA_VERSION and adds a migration step;
a file written by a newer version is refused rather than guessed at.

Moving to Postgres later (T30) means porting this file and `app/engine/cache.py`; nothing else touches SQL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app import config

SCHEMA_VERSION = 1
FILE_NAME = "coach.sqlite3"

_SCHEMA_V1 = """
CREATE TABLE engine_config (
    id                TEXT PRIMARY KEY,
    version           TEXT NOT NULL,
    network           TEXT NOT NULL,
    binary_sha256     TEXT NOT NULL,
    depth             INTEGER NOT NULL,
    multipv           INTEGER NOT NULL,
    hash_mb           INTEGER NOT NULL,
    threads           INTEGER NOT NULL,
    score_perspective TEXT NOT NULL CHECK (score_perspective IN ('white')),
    created_at        TEXT NOT NULL
) STRICT;

CREATE TABLE engine_analysis (
    fen              TEXT NOT NULL,
    engine_config_id TEXT NOT NULL REFERENCES engine_config(id),
    lines_json       TEXT NOT NULL,
    analysed_at      TEXT NOT NULL,
    PRIMARY KEY (fen, engine_config_id)
) STRICT;

CREATE TABLE game (
    id                      TEXT PRIMARY KEY,
    source                  TEXT NOT NULL CHECK (source IN ('chesscom', 'inapp')),
    platform_id             TEXT NOT NULL,
    time_control            TEXT NOT NULL,
    played_at               INTEGER NOT NULL,
    pool                    TEXT NOT NULL CHECK (pool IN ('PRACTICE', 'HELDOUT')),
    pgn                     TEXT NOT NULL,
    analyzed_with_config_id TEXT REFERENCES engine_config(id),
    UNIQUE (source, platform_id)
) STRICT;

CREATE TRIGGER game_pool_is_final BEFORE UPDATE OF pool ON game
WHEN NEW.pool IS NOT OLD.pool
BEGIN SELECT RAISE(ABORT, 'a game never changes pool'); END;

CREATE TABLE position (
    id                         INTEGER PRIMARY KEY,
    game_id                    TEXT REFERENCES game(id),
    ply                        INTEGER,
    fen                        TEXT NOT NULL,
    kind                       TEXT NOT NULL CHECK (kind IN ('MISTAKE', 'CLEAN', 'CURATED')),
    mistake_type               TEXT CHECK (mistake_type IN ('M1', 'M2')),
    source_tag                 TEXT NOT NULL CHECK (source_tag IN ('chesscom', 'inapp', 'curated')),
    pool                       TEXT NOT NULL CHECK (pool IN ('PRACTICE', 'HELDOUT')),
    original_move              TEXT,
    evidence_json              TEXT,
    verified_alternatives_json TEXT,
    exposure_status            TEXT NOT NULL DEFAULT 'UNSEEN'
                               CHECK (exposure_status IN ('UNSEEN', 'PRACTICED', 'TESTED')),
    excluded_reason            TEXT,  -- set when the owner has already seen it (audit C5); never assessed
    engine_config_id           TEXT NOT NULL REFERENCES engine_config(id),
    detector_version           TEXT NOT NULL,
    CHECK ((kind = 'MISTAKE') = (mistake_type IS NOT NULL)),
    CHECK (exposure_status = 'UNSEEN'
           OR (exposure_status = 'PRACTICED' AND pool = 'PRACTICE')
           OR (exposure_status = 'TESTED' AND pool = 'HELDOUT')),
    UNIQUE (game_id, ply, kind, mistake_type, engine_config_id, detector_version)
) STRICT;

CREATE TRIGGER position_pool_matches_game BEFORE INSERT ON position
WHEN NEW.game_id IS NOT NULL AND NEW.pool IS NOT (SELECT pool FROM game WHERE id = NEW.game_id)
BEGIN SELECT RAISE(ABORT, 'a position takes the pool of its game'); END;

CREATE TRIGGER position_pool_is_final BEFORE UPDATE OF pool, game_id ON position
WHEN NEW.pool IS NOT OLD.pool OR NEW.game_id IS NOT OLD.game_id
BEGIN SELECT RAISE(ABORT, 'a position never changes pool or game'); END;

CREATE TRIGGER position_tested_is_final BEFORE UPDATE OF exposure_status ON position
WHEN OLD.exposure_status = 'TESTED' AND NEW.exposure_status IS NOT 'TESTED'
BEGIN SELECT RAISE(ABORT, 'a tested position is never reused'); END;

CREATE TABLE practice_session (
    id           INTEGER PRIMARY KEY,
    user         TEXT NOT NULL,
    mistake_type TEXT NOT NULL CHECK (mistake_type IN ('M1', 'M2')),
    status       TEXT NOT NULL CHECK (status IN ('created', 'in_progress', 'completed', 'abandoned')),
    started_at   TEXT NOT NULL,
    completed_at TEXT
) STRICT;

CREATE TABLE practice_attempt (
    id                   INTEGER PRIMARY KEY,
    session_id           INTEGER NOT NULL REFERENCES practice_session(id),
    position_id          INTEGER NOT NULL REFERENCES position(id),
    attempt_number       INTEGER NOT NULL CHECK (attempt_number >= 1),
    recognition_response TEXT,
    move                 TEXT,
    move_sound           INTEGER CHECK (move_sound IN (0, 1)),
    hint_level           INTEGER NOT NULL DEFAULT 0 CHECK (hint_level BETWEEN 0 AND 3),
    elapsed_ms           INTEGER,
    created_at           TEXT NOT NULL,
    UNIQUE (session_id, position_id, attempt_number)
) STRICT;

CREATE TRIGGER practice_uses_practice_pool BEFORE INSERT ON practice_attempt
WHEN (SELECT pool FROM position WHERE id = NEW.position_id) IS NOT 'PRACTICE'
BEGIN SELECT RAISE(ABORT, 'practice never uses a held-out position'); END;

CREATE TABLE assessment (
    id                INTEGER PRIMARY KEY,
    user              TEXT NOT NULL,
    mistake_type      TEXT NOT NULL CHECK (mistake_type IN ('M1', 'M2')),
    kind              TEXT NOT NULL CHECK (kind IN ('BASELINE', 'DELAYED')),
    source_session_id INTEGER REFERENCES practice_session(id),
    created_at        TEXT NOT NULL,
    due_at            TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'submitted')),
    position_ids_json TEXT NOT NULL,
    submitted_at      TEXT,
    CHECK ((kind = 'DELAYED') = (source_session_id IS NOT NULL))
) STRICT;

CREATE UNIQUE INDEX one_open_assessment_per_type
ON assessment (user, mistake_type) WHERE status <> 'submitted';

CREATE TABLE assessment_result (
    id                   INTEGER PRIMARY KEY,
    assessment_id        INTEGER NOT NULL REFERENCES assessment(id),
    position_id          INTEGER NOT NULL REFERENCES position(id),
    recognition_response TEXT,
    recognition_correct  INTEGER CHECK (recognition_correct IN (0, 1)),
    move                 TEXT,
    move_sound           INTEGER CHECK (move_sound IN (0, 1)),
    elapsed_ms           INTEGER CHECK (elapsed_ms BETWEEN 0 AND 300000),
    interrupted          INTEGER NOT NULL DEFAULT 0 CHECK (interrupted IN (0, 1)),
    UNIQUE (assessment_id, position_id)
) STRICT;

CREATE TRIGGER assessment_uses_heldout_pool BEFORE INSERT ON assessment_result
WHEN (SELECT pool FROM position WHERE id = NEW.position_id) IS NOT 'HELDOUT'
BEGIN SELECT RAISE(ABORT, 'assessments only use held-out positions'); END;

CREATE TABLE baseline_window (
    id           INTEGER PRIMARY KEY,
    user         TEXT NOT NULL,
    mistake_type TEXT NOT NULL CHECK (mistake_type IN ('M1', 'M2')),
    time_control TEXT NOT NULL,
    game_ids_json TEXT NOT NULL,
    frozen_at    TEXT NOT NULL,
    UNIQUE (user, mistake_type, time_control)
) STRICT;

CREATE TRIGGER baseline_window_no_update BEFORE UPDATE ON baseline_window
BEGIN SELECT RAISE(ABORT, 'a frozen baseline window is never edited'); END;

CREATE TRIGGER baseline_window_no_delete BEFORE DELETE ON baseline_window
BEGIN SELECT RAISE(ABORT, 'a frozen baseline window is never deleted'); END;

CREATE TABLE realgame_stat (
    window                 TEXT NOT NULL,
    time_control           TEXT NOT NULL,
    mistake_type           TEXT NOT NULL CHECK (mistake_type IN ('M1', 'M2')),
    games                  INTEGER NOT NULL,
    moves_or_opportunities INTEGER NOT NULL,
    events                 INTEGER NOT NULL,
    engine_config_id       TEXT NOT NULL REFERENCES engine_config(id),
    computed_at            TEXT NOT NULL,
    PRIMARY KEY (window, time_control, mistake_type, engine_config_id)
) STRICT;
"""

_MIGRATIONS = {1: _SCHEMA_V1}  # version -> SQL that brings version - 1 up to it


class SchemaError(Exception):
    pass


def default_path() -> Path:
    return config.DATA_DIR / FILE_NAME


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open (and if needed create or upgrade) the store. `":memory:"` gives a throwaway store for tests."""
    target = default_path() if path is None else path
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, isolation_level=None)  # autocommit; use `with transaction(conn)` to group
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if target != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise SchemaError(f"store is schema {current}, this code knows up to {SCHEMA_VERSION}")
    for version in range(current + 1, SCHEMA_VERSION + 1):
        with transaction(conn):
            for statement in _split(_MIGRATIONS[version]):
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version}")


def _split(script: str) -> list[str]:
    """Split a schema script into statements; trigger bodies keep their inner semicolons."""
    statements, buf = [], []
    for line in script.strip().splitlines():
        buf.append(line)
        joined = "\n".join(buf).strip()
        if sqlite3.complete_statement(joined):
            statements.append(joined)
            buf = []
    if "\n".join(buf).strip():
        raise SchemaError("incomplete statement at the end of the schema")
    return statements


class transaction:
    """`with transaction(conn):` runs the block as one all-or-nothing change."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, *_) -> None:
        self.conn.execute("ROLLBACK" if exc_type else "COMMIT")
