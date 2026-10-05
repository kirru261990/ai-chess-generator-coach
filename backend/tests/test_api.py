from fastapi.testclient import TestClient

from app.api.main import app
from app.mcp.server import get_game as mcp_get_game

client = TestClient(app)


def test_play_flow_and_errors():
    g = client.post("/games", json={}).json()
    gid = g["id"]
    r = client.post(f"/games/{gid}/moves", json={"uci": "e2e4", "expected_revision": 0})
    assert r.status_code == 200 and r.json()["revision"] == 1
    r = client.post(f"/games/{gid}/moves", json={"uci": "e7e5", "expected_revision": 0})
    assert r.status_code == 409 and r.json()["error"] == "revision_conflict"
    r = client.post(f"/games/{gid}/moves", json={"uci": "e7e3", "expected_revision": 1})
    assert r.status_code == 400 and r.json()["error"] == "illegal_move"
    assert client.get("/games/nope").status_code == 404
    assert "1. e4" in client.get(f"/games/{gid}/pgn").text


def test_mcp_get_game_matches_api():
    gid = client.post("/games", json={"mode": "practice"}).json()["id"]
    assert mcp_get_game(gid) == client.get(f"/games/{gid}").json()
    assert mcp_get_game(gid)["assisted"] is True
