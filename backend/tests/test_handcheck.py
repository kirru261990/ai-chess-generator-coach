"""Step 1c hand-check: the sample stays out of the test pool and is frozen; the score rule is strict."""

import json

import pytest

from app.db.schema import connect
from app.learner import handcheck

M1_FEN = "4k3/4q3/8/8/8/8/3B4/6KR w - - 0 1"
M2_FEN = "4k3/8/8/7r/8/8/8/3QK3 w - - 0 1"


def m1(lost):
    return {"mistake_type": "M1", "fen": M1_FEN, "ply": 10, "player_move": {"uci": "h1h7", "san": "Rh7"},
            "target_squares": ["h1"], "lost_piece": lost, "lost_piece_square_after": "h7",
            "refutation_line": {"uci": ["e7h7", "g1f1"], "san": ["Qxh7", "Kf1"]}, "material_swing": 5,
            "eval_loss": 650, "eval_loss_stability": 640}


M2 = {"mistake_type": "M2", "fen": M2_FEN, "ply": 12, "player_move": {"uci": "e1f1", "san": "Kf1"},
      "target_squares": ["h5"], "refutation_line": {"uci": ["d1h5", "e8d7"], "san": ["Qxh5+", "Kd7"]},
      "material_swing": 5, "eval_loss": 600, "eval_loss_stability": 590}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(handcheck.config, "DATA_DIR", tmp_path)
    conn = connect(":memory:")
    conn.execute("INSERT INTO engine_config VALUES ('ec', 'Stockfish 19', 'nn', 'abc', 18, 3, 64, 1, 'white', 'x')")
    for pool in ("PRACTICE", "HELDOUT"):
        for n in range(40):
            gid = f"{pool}-{n}"
            conn.execute("INSERT INTO game (id, source, platform_id, user_color, time_control, played_at, pool, pgn)"
                         " VALUES (?, 'chesscom', ?, 'white', '600', 0, ?, '')", (gid, gid, pool))
            for ply, mtype, ev in ((10, "M1", m1("moved" if n % 2 else "other")), (12, "M2", M2)):
                conn.execute(
                    "INSERT INTO position (game_id, ply, fen, kind, mistake_type, source_tag, pool, original_move,"
                    " evidence_json, verified_alternatives_json, engine_config_id, detector_version)"
                    " VALUES (?, ?, ?, 'MISTAKE', ?, 'chesscom', ?, ?, ?, ?, 'ec', 'v3')",
                    (gid, ply, ev["fen"], mtype, pool, ev["player_move"]["uci"], json.dumps(ev),
                     json.dumps([{"uci": "h1h2" if mtype == "M1" else "d1h5", "san": "x"}])))
    conn.execute("UPDATE position SET excluded_reason = 'shown_in_explorer' WHERE game_id = 'PRACTICE-0'")
    return conn


def test_sample_is_practice_only_unseen_and_stratified(db):
    page = handcheck.make(db)
    key = json.loads(handcheck.key_path().read_text())
    ids = [it["position_id"] for it in key["items"]]
    assert len(ids) == 30 and len(set(ids)) == 30
    rows = db.execute(f"SELECT pool, game_id, mistake_type, evidence_json FROM position WHERE id IN ({','.join('?' * 30)})",
                      ids).fetchall()
    assert {r["pool"] for r in rows} == {"PRACTICE"}
    assert "PRACTICE-0" not in {r["game_id"] for r in rows}  # already seen on the explorer page
    lost = [json.loads(r["evidence_json"]).get("lost_piece") for r in rows if r["mistake_type"] == "M1"]
    assert (lost.count("moved"), lost.count("other"), sum(r["mistake_type"] == "M2" for r in rows)) == (8, 7, 15)
    marked = db.execute("SELECT COUNT(*) FROM position WHERE excluded_reason = ?", (handcheck.MARK,)).fetchone()[0]
    assert marked == 30
    text = page.read_text()
    assert text.count('class="card"') == 31 and "hc-30" in text  # 30 positions and the final card


def test_second_make_rebuilds_without_resampling(db):
    handcheck.make(db)
    first = handcheck.key_path().read_text()
    handcheck.make(db)
    assert handcheck.key_path().read_text() == first


def test_score_counts_only_all_yes_as_real(db):
    handcheck.make(db)
    items = json.loads(handcheck.key_path().read_text())["items"]
    lines = []
    for n, it in enumerate(items):
        if n == 0:
            lines.append(f"{it['id']}: A cant" + (", B -" if it["type"] == "M1" else ""))
        elif n == 1:
            lines.append(f"{it['id']}: A no" + (", B -" if it["type"] == "M1" else ""))
        else:
            lines.append(f"{it['id']}: A yes" + (", B yes" if it["type"] == "M1" else ""))
    result = handcheck.score(db, "\n".join(lines))
    assert (result["real"], result["of"], result["passed"]) == (28, 30, True)
    assert [i["id"] for i in result["not_real"]] == [items[0]["id"], items[1]["id"]]
    assert result["unanswered"] == []


def test_gate_fails_below_27_and_missing_answers_are_listed(db):
    handcheck.make(db)
    items = json.loads(handcheck.key_path().read_text())["items"]
    m1 = [it for it in items if it["type"] == "M1"]
    rest = [it for it in items if it not in m1[:4]]
    lines = [f"{it['id']}: A yes, B no" for it in m1[:4]]  # B no: the piece was lost anyway
    lines += [f"{it['id']}: A yes" + (", B yes" if it["type"] == "M1" else "") for it in rest[:-1]]
    result = handcheck.score(db, "\n".join(lines))
    assert result["real"] == 25 and not result["passed"]
    assert result["unanswered"] == [rest[-1]["id"]]


def test_line_words_label_moves_from_the_players_side():
    import chess

    board = chess.Board(M1_FEN)
    board.push_uci("h1h7")  # White's mistake; Black replies
    assert handcheck.line_words(board, ["e7h7", "g1f1"], chess.WHITE) == \
        "they: queen takes the rook on h7; you: king to f1"
