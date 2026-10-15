"""The SQLite store for PRD v2 (ADR 0006): games, pools, positions, sessions, assessments, engine cache.

One file under `data/` (git-ignored), opened with the standard library's `sqlite3`. The rules that must never
be broken are enforced by the database itself, not only by the code that writes to it (PRD §5, §10):

- a game's pool is set once and never changes; a position's pool equals its game's pool and never changes
- PRACTICED is only possible in the PRACTICE pool, TESTED only in the HELDOUT pool, and TESTED is final
- practice attempts only use PRACTICE positions, also when an attempt is later changed
- a held-out position is allocated to at most one assessment, ever; a TESTED or excluded position is never allocated;
  an assessment result must answer a position allocated to that assessment
- a game-derived position is stored once per (game, ply, kind, mistake type, config, detector version), CLEAN included
- at most one unsubmitted assessment per user and mistake type
- a frozen real-game baseline window is never edited or deleted

`connect()` creates the tables on first use and upgrades older files: a new store runs every migration from v1, so a new
store and an upgraded one are the same. A schema change never edits a released step; it bumps SCHEMA_VERSION and adds one.
A file written by a newer version is refused rather than guessed at.

Moving to Postgres later (T30) means porting this file and `app/engine/cache.py`; nothing else touches SQL.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from app import config

SCHEMA_VERSION = 4
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
           OR (exposure_status = 'TESTED' AND pool = 'HELDOUT'))
) STRICT;

-- NULL-safe: CLEAN positions have no mistake type, and a plain UNIQUE treats NULLs as distinct.
CREATE UNIQUE INDEX position_once_per_analysis
ON position (game_id, ply, kind, IFNULL(mistake_type, ''), engine_config_id, detector_version)
WHERE game_id IS NOT NULL;

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

CREATE TRIGGER practice_uses_practice_pool_on_update BEFORE UPDATE OF position_id ON practice_attempt
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
    submitted_at      TEXT,
    CHECK ((kind = 'DELAYED') = (source_session_id IS NOT NULL))
) STRICT;

CREATE UNIQUE INDEX one_open_assessment_per_type
ON assessment (user, mistake_type) WHERE status <> 'submitted';

-- The positions allocated to an assessment (PRD §10 `position_ids`), in the order shown. A position is allocated once, ever.
CREATE TABLE assessment_position (
    assessment_id INTEGER NOT NULL REFERENCES assessment(id),
    position_id   INTEGER NOT NULL UNIQUE REFERENCES position(id),
    ord           INTEGER NOT NULL CHECK (ord >= 0),
    PRIMARY KEY (assessment_id, position_id),
    UNIQUE (assessment_id, ord)
) STRICT;

CREATE TRIGGER assessment_allocates_unseen_heldout BEFORE INSERT ON assessment_position
WHEN (SELECT pool IS NOT 'HELDOUT' OR exposure_status = 'TESTED' OR excluded_reason IS NOT NULL
      FROM position WHERE id = NEW.position_id)
BEGIN SELECT RAISE(ABORT, 'assessments only use unseen held-out positions'); END;

CREATE TRIGGER assessment_position_is_final BEFORE UPDATE ON assessment_position
BEGIN SELECT RAISE(ABORT, 'an allocation is never changed'); END;

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
    UNIQUE (assessment_id, position_id),
    -- the answer must be for a position allocated to this assessment (which is held-out, unseen and not excluded)
    FOREIGN KEY (assessment_id, position_id) REFERENCES assessment_position (assessment_id, position_id)
) STRICT;

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



def _v2_user_color(conn: sqlite3.Connection) -> None:
    """v2 (Step 1b): `game.user_color`, which side the player had. Existing games are filled from the PGN's White/Black
    names and CHESSCOM_USERNAME; any game still unknown is filled by the next `pools.import_games`, and the runner skips it
    until then. A new game without a colour is refused. Safe on a v1 store that already has the column (a Step 1b
    development build wrote one)."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(game)")}
    if "user_color" not in columns:
        conn.execute("ALTER TABLE game ADD COLUMN user_color TEXT CHECK (user_color IN ('white', 'black'))")
    username = (config.chesscom_username() or "").lower()
    if username:
        for row in conn.execute("SELECT id, pgn FROM game WHERE user_color IS NULL").fetchall():
            color = _pgn_color(row["pgn"], username)
            if color:
                conn.execute("UPDATE game SET user_color = ? WHERE id = ?", (color, row["id"]))
    conn.execute(
        "CREATE TRIGGER IF NOT EXISTS game_user_color_required BEFORE INSERT ON game WHEN NEW.user_color IS NULL"
        " BEGIN SELECT RAISE(ABORT, 'a game needs the player''s colour'); END"
    )


_PGN_PLAYER = re.compile(r'^\[(White|Black) "([^"]*)"\]', re.MULTILINE)


def _pgn_color(pgn: str, username: str) -> str | None:
    """'white' / 'black' when the PGN header names `username` on exactly one side (headers only; the rest is untrusted)."""
    names = {tag.lower(): value.lower() for tag, value in _PGN_PLAYER.findall(pgn)}
    sides = [side for side in ("white", "black") if names.get(side) == username]
    return sides[0] if len(sides) == 1 else None


def _v3_retired(conn: sqlite3.Connection) -> None:
    """v3: `position.retired_at`. A detector fix leaves old rows in place but retired: they keep their history and their
    "seen" marks (a board the owner saw stays seen), and they are never allocated, practised or counted again."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(position)")}
    if "retired_at" not in columns:
        conn.execute("ALTER TABLE position ADD COLUMN retired_at TEXT")
    for table, message in (("assessment_position", "a retired position is never assessed"),
                           ("practice_attempt", "a retired position is never practised")):
        conn.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_not_retired BEFORE INSERT ON {table}"
            f" WHEN (SELECT retired_at FROM position WHERE id = NEW.position_id) IS NOT NULL"
            f" BEGIN SELECT RAISE(ABORT, '{message}'); END"
        )


def _v4_retired_on_update(conn: sqlite3.Connection) -> None:
    """v4 (review on PR 65): the v3 guard ran on INSERT only, so an existing practice attempt could be pointed at a retired
    position. Assessment answers need no new guard: they must match an allocation, and allocations are never changed."""
    conn.execute(
        "CREATE TRIGGER IF NOT EXISTS practice_attempt_not_retired_on_update BEFORE UPDATE OF position_id ON practice_attempt"
        " WHEN (SELECT retired_at FROM position WHERE id = NEW.position_id) IS NOT NULL"
        " BEGIN SELECT RAISE(ABORT, 'a retired position is never practised'); END"
    )


# version -> SQL text, or a function, that brings version - 1 up to it
_MIGRATIONS = {1: _SCHEMA_V1, 2: _v2_user_color, 3: _v3_retired, 4: _v4_retired_on_update}


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
    conn.execute("PRAGMA busy_timeout = 30000")  # several engine processes may write the cache at once
    if target != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise SchemaError(f"store is schema {current}, this code knows up to {SCHEMA_VERSION}")
    for version in range(current + 1, SCHEMA_VERSION + 1):
        step = _MIGRATIONS[version]
        with transaction(conn):
            if callable(step):
                step(conn)
            else:
                for statement in _split(step):
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
