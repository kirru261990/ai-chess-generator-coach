"""The explorer page never shows a held-out position, and marks what it shows (PRD v2 §5.3)."""

import json

import chess

from app.db.schema import connect
from app.learner import explorer

FEN = "4k3/4q3/8/8/8/8/3B4/6KR w - - 0 1"
M1 = {"mistake_type": "M1", "fen": FEN, "ply": 10, "player_move": {"uci": "h1h7", "san": "Rh7"},
      "target_squares": ["h1"], "lost_piece": "moved", "lost_piece_square_after": "h7",
      "refutation_line": {"uci": ["e7h7"], "san": ["Qxh7"]}, "eval_loss": 650}


def store():
    conn = connect(":memory:")
    conn.execute("INSERT INTO engine_config VALUES ('ec', 'Stockfish 19', 'nn', 'abcdef123456', 18, 3, 64, 1, 'white', 'x')")
    for gid, pool in (("gp", "PRACTICE"), ("gh", "HELDOUT")):
        conn.execute("INSERT INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
                     " VALUES (?, 'chesscom', ?, 'white', '600', 0, ?, '')", (gid, gid, pool))
        for ply in range(5):
            conn.execute(
                "INSERT INTO position (game_id, ply, fen, kind, mistake_type, source_tag, pool, original_move,"
                " evidence_json, verified_alternatives_json, engine_config_id, detector_version)"
                " VALUES (?, ?, ?, 'MISTAKE', 'M1', 'chesscom', ?, 'h1h7', ?, ?, 'ec', 'v3')",
                (gid, ply, FEN, pool, json.dumps(M1), json.dumps([{"uci": "h1h2", "san": "Rh2"}])))
    return conn


def test_only_practice_positions_are_shown_and_they_are_marked():
    conn = store()
    page = explorer.build(conn, per_type=3)
    assert "Hanging piece" in page and "rook to h7" in page
    marked = conn.execute("SELECT pool, COUNT(*) FROM position WHERE excluded_reason = ? GROUP BY pool",
                          (explorer.SHOWN,)).fetchall()
    assert [tuple(r) for r in marked] == [("PRACTICE", 3)]


def test_a_second_page_shows_the_same_positions_not_new_ones():
    conn = store()
    explorer.build(conn, per_type=3)
    explorer.build(conn, per_type=3)
    assert conn.execute("SELECT COUNT(*) FROM position WHERE excluded_reason = ?", (explorer.SHOWN,)).fetchone()[0] == 3


def test_plain_words_have_no_notation():
    assert explorer.plain(chess.Board(FEN), "h1h7") == "rook to h7"
    assert explorer.plain(chess.Board(FEN), "d2g5") == "bishop to g5"
