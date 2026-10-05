import os
import shutil

import chess
import pytest
from fastapi.testclient import TestClient

from app.api import tools
from app.api.main import app
from app.api.store import GAMES
from app.core.game import new_game
from app.mcp.server import get_game as mcp_get_game

client = TestClient(app)
needs_engine = pytest.mark.skipif(
    not (os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")),
    reason="Stockfish not installed",
)


def move(gid, uci, rev, **extra):
    return client.post(f"/games/{gid}/moves", json={"uci": uci, "expected_revision": rev, **extra})


def test_errors_use_stable_codes():
    gid = client.post("/games", json={}).json()["id"]
    assert client.post("/games", json={"level": 99}).json()["error"] == "invalid_level"
    assert client.post("/games", json={"color": "green"}).json()["error"] == "invalid_color"
    assert client.get("/games/nope").status_code == 404
    r = move(gid, "e2e4", 5, engine_reply=False)
    assert r.status_code == 409 and r.json()["error"] == "revision_conflict"
    r = move(gid, "e2e5", 0, engine_reply=False)
    assert r.status_code == 400 and r.json()["error"] == "illegal_move"


def test_move_without_engine_reply_leaves_engine_turn_pending():
    gid = client.post("/games", json={}).json()["id"]
    r = move(gid, "e2e4", 0, engine_reply=False).json()
    assert r["revision"] == 1 and r["turn"] == "black"
    # opponent's turn: the user cannot move for them
    r = move(gid, "e7e5", 1, engine_reply=False)
    assert r.status_code == 409 and r.json()["error"] == "not_your_turn"


@needs_engine
def test_engine_replies_after_user_move():
    gid = client.post("/games", json={"level": 1}).json()["id"]
    r = move(gid, "e2e4", 0).json()
    assert r["revision"] == 2 and r["turn"] == "white"
    assert "1. e4" in client.get(f"/games/{gid}/pgn").text


@needs_engine
def test_engine_opens_when_user_plays_black():
    g = client.post("/games", json={"color": "black", "level": 1}).json()
    assert g["revision"] == 1 and g["turn"] == "black" and g["user_color"] == "black"
    pgn = client.get(f"/games/{g['id']}/pgn").text
    assert '[Black "You"]' in pgn and '[White "Stockfish Level 1"]' in pgn


@needs_engine
def test_engine_move_is_idempotent_on_users_turn():
    gid = client.post("/games", json={}).json()["id"]
    before = client.get(f"/games/{gid}").json()
    after = client.post(f"/games/{gid}/engine-move").json()
    assert before == after


@needs_engine
def test_engine_move_ends_game_by_checkmate():
    # user (black) to defend against Ra8#; after the user's turn passes the engine mates
    game = new_game(chess.BLACK, engine_level=10, start_fen="6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1")
    GAMES[game.id] = game
    r = client.post(f"/games/{game.id}/engine-move").json()
    assert r["outcome"] == {"result": "1-0", "termination": "checkmate"}
    # nothing more can happen after the game ends
    assert move(game.id, "g8f8", r["revision"]).status_code in (400, 409)


def test_resign_ends_game_and_blocks_moves():
    gid = client.post("/games", json={}).json()["id"]
    r = client.post(f"/games/{gid}/resign").json()
    assert r["outcome"] == {"result": "0-1", "termination": "resignation"}
    assert move(gid, "e2e4", r["revision"], engine_reply=False).status_code == 400


def test_mcp_get_game_matches_api():
    gid = client.post("/games", json={"mode": "practice", "color": "white"}).json()["id"]
    assert mcp_get_game(gid) == client.get(f"/games/{gid}").json()
    assert mcp_get_game(gid)["assisted"] is True


def test_game_view_has_engine_level():
    assert tools.start_game(level=4)["engine_level"] == 4


def test_play_game_is_unassisted_and_practice_game_starts_assisted():
    assert client.post("/games", json={"mode": "play"}).json()["assisted"] is False
    assert client.post("/games", json={"mode": "practice"}).json()["assisted"] is True
    assert client.post("/games", json={"mode": "cheat"}).json()["error"] == "invalid_mode"


def test_switching_to_practice_marks_assisted_permanently():
    gid = client.post("/games", json={"mode": "play"}).json()["id"]
    r = client.post(f"/games/{gid}/mode", json={"mode": "practice"}).json()
    assert r["mode"] == "practice" and r["assisted"] is True
    r = client.post(f"/games/{gid}/mode", json={"mode": "play"}).json()
    assert r["mode"] == "play" and r["assisted"] is True  # never reverts
    assert 'Assisted "true"' in client.get(f"/games/{gid}/pgn").text.replace("[", "").replace("]", "")


def test_mode_switch_does_not_change_revision_and_rejects_bad_input():
    gid = client.post("/games", json={}).json()["id"]
    assert client.post(f"/games/{gid}/mode", json={"mode": "practice"}).json()["revision"] == 0
    assert client.post(f"/games/{gid}/mode", json={"mode": "x"}).json()["error"] == "invalid_mode"
    assert client.post("/games/nope/mode", json={"mode": "play"}).status_code == 404


def test_cors_allows_any_local_dev_port_but_not_other_sites():
    def preflight(origin):
        return client.options(
            "/games", headers={"Origin": origin, "Access-Control-Request-Method": "POST"}
        )

    for ok in ("http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5199"):
        assert preflight(ok).headers.get("access-control-allow-origin") == ok
    for bad in ("https://evil.example", "http://localhost.evil.example", "http://example.com:5173"):
        assert "access-control-allow-origin" not in preflight(bad).headers
