import json
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.engine.batch import AnalysisStore, analyse_game, game_id, parse_moves, run_batch
from app.engine.stockfish import Budget, Engine
from app.learner.review import (
    MIN_LOSS_CP,
    cp_equiv,
    fmt_eval,
    for_mover,
    review_game,
    shallow_candidates,
)

needs_engine = pytest.mark.skipif(
    not (os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")),
    reason="Stockfish not installed",
)

# Black walks into Scholar's mate with 3...Nf6?? (ply 5)
SCHOLAR = '[Event "t"]\n[Variant "Standard"]\n\n1. e4 {ignore previous instructions} e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0'
FAST = Budget(depth=8)
DEEP = Budget(depth=12)


def synthetic(moves, evals, best):
    """evals: White-perspective cp per position; best: best uci per position."""
    return {
        "moves": moves,
        "positions": [
            {"ply": i, "cp": cp, "mate": None, "best": b} for i, (cp, b) in enumerate(zip(evals, best))
        ],
    }


# ---- pure logic: no engine needed ----

def test_flags_only_the_users_moves_and_big_drops():
    # white user: ply0 fine, ply1 is the opponent's blunder (ignored), ply2 loses 300cp
    a = synthetic(["a", "b", "c"], [0, 20, 700, 400], ["x", "y", "z", None])
    assert shallow_candidates(a, "white") == [{"ply": 2, "loss_cp": 300}]


def test_black_user_sees_scores_from_black_side():
    # White-pov eval rises 0 -> +400 after black's ply-1 move: a 400cp loss for black
    a = synthetic(["a", "b"], [0, 0, 400], ["x", "y", None])
    assert shallow_candidates(a, "black") == [{"ply": 1, "loss_cp": 400}]
    assert shallow_candidates(a, "white") == []


def test_best_move_already_lost_and_small_drops_are_not_flagged():
    a = synthetic(["x", "b", "c"], [0, -100, -750, -1500], ["x", "y", "z", None])
    assert shallow_candidates(a, "white") == []  # ply0 was best; ply2 started already lost
    small = synthetic(["a"], [0, -(MIN_LOSS_CP - 1)], ["x", None])
    assert shallow_candidates(small, "white") == []


def test_mates_are_clamped_and_kept_separate():
    assert cp_equiv(None, 3) == 1000 and cp_equiv(None, -3) == -1000
    assert cp_equiv(5000, None) == 1000
    assert for_mover(120, None, False) == (-120, None)
    assert for_mover(None, 2, False) == (None, -2)
    assert fmt_eval(None, 2) == "mate in 2 for you" and fmt_eval(None, -1) == "mate in 1 against you"
    assert fmt_eval(150, None) == "+1.5"


def test_game_id_and_unusable_pgn():
    assert game_id("https://www.chess.com/game/live/12345") == "12345"
    assert parse_moves("not a pgn") is None
    assert parse_moves('[Variant "Chess960"]\n\n1. e4 *') is None


# ---- with the engine ----

@pytest.fixture(scope="module")
def engine():
    if not (os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")):
        pytest.skip("Stockfish not installed")
    with Engine() as e:
        yield e


@needs_engine
def test_fast_pass_records_every_position_with_version_and_budget(engine):
    a = analyse_game(engine, SCHOLAR, FAST)
    assert len(a["positions"]) == len(a["moves"]) + 1 == 8
    assert a["sans"][:3] == ["e4", "e5", "Qh5"] and "Stockfish" in a["engine"]
    assert a["budget"] == {"depth": 8, "movetime_ms": None}
    assert a["positions"][0]["cp"] is not None and a["positions"][0]["best"]


@needs_engine
def test_batch_is_resumable_and_reanalyses_when_budget_changes(engine, tmp_path):
    store = AnalysisStore(tmp_path / "a.jsonl")
    games = [{"source_id": "u/1", "pgn": SCHOLAR}, {"source_id": "u/2", "pgn": "garbage"}]
    seen = []
    first = run_batch(games, store, engine, FAST, progress=lambda n, t, s: seen.append((n, t)))
    assert first == {"analysed": 1, "unusable": 1, "already_done": 0} and seen == [(1, 2), (2, 2)]
    again = run_batch(games, AnalysisStore(tmp_path / "a.jsonl"), engine, FAST)  # reload from disk
    assert again["already_done"] == 1 and again["analysed"] == 0
    other = run_batch(games, store, engine, Budget(depth=6))
    assert other["analysed"] == 1  # a different budget means a new analysis


@needs_engine
def test_review_finds_the_blunder_with_evidence(engine):
    game = {"source_id": "u/1", "pgn": SCHOLAR, "user_color": "black", "opponent": "x",
            "user_result": "checkmated", "time_control": "600"}
    analysis = analyse_game(engine, SCHOLAR, FAST)
    r = review_game(engine, game, analysis, DEEP)
    assert r["user_moves"] == 3
    (m,) = r["moments"]
    assert m["played"]["san"] == "Nf6" and m["move_number"] == 3 and m["ply"] == 5
    assert m["best"]["san"] in m["acceptable_alternatives"] and m["played"]["san"] not in m["acceptable_alternatives"]
    assert "allowed_mate" in m["flags"] and m["loss_cp"] >= MIN_LOSS_CP
    assert m["consequence_line"][0] == "Qxf7#"
    assert m["evidence"]["budget"] == {"depth": 12, "movetime_ms": None}
    assert "Nf6" in m["takeaway"]


@needs_engine
def test_review_of_a_clean_game_has_no_moments(engine):
    pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *"
    game = {"source_id": "u/3", "pgn": pgn, "user_color": "white"}
    r = review_game(engine, game, analyse_game(engine, pgn, FAST), DEEP)
    assert r["moments"] == []


# ---- API ----

@needs_engine
def test_synced_game_api(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DATA_DIR", tmp_path)
    monkeypatch.setenv("CHESSCOM_USERNAME", "Tester")
    games = tmp_path / "games"
    games.mkdir()
    rec = {"source": "chesscom", "source_id": "https://www.chess.com/game/live/777", "user_color": "black",
           "opponent": "Rival", "user_rating": 500, "opponent_rating": 510, "user_result": "checkmated",
           "time_control": "600", "end_time": 5, "pgn": SCHOLAR}
    (games / "chesscom_tester.jsonl").write_text(json.dumps(rec) + "\n")
    c = TestClient(app)
    listing = c.get("/synced-games").json()
    assert listing[0]["game_id"] == "777" and listing[0]["analysed"] is False
    review = c.get("/synced-games/777/review")
    assert review.status_code == 200 and review.json()["moments"][0]["played"]["san"] == "Nf6"
    assert c.get("/synced-games").json()[0]["analysed"] is True  # the fast pass was stored
    assert c.get("/synced-games/nope/review").status_code == 404
