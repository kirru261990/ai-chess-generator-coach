"""The open (public) MCP server: games only, no login, no database, no model, and bounded."""

import asyncio

import chess
import pytest
from starlette.testclient import TestClient

from app.api import tools
from app.mcp import game_tools as G
from app.mcp import server as S

PUBLIC_URL = "https://chess.example.org"
GAME_TOOLS = {"game_new", "game_show", "game_move", "game_resign", "game_undo", "game_hint", "game_threats",
              "game_apply_move", "game_engine_move"}


class FakeEngine:
    def play(self, board, level, movetime_ms=0):
        return min(m.uci() for m in board.legal_moves)


@pytest.fixture(autouse=True)
def engine(monkeypatch):
    monkeypatch.setattr(tools, "get_engine", lambda: FakeEngine())
    monkeypatch.setattr(tools, "move_feedback", lambda gid, ply: {
        "ply": ply, "verdict": "good", "headline": "A fine move", "classification": {"key": "good", "opening": None},
        "marks": {"own_hanging": [], "missed_free": []}, "played": {"uci": "x", "text": "x"}, "better_move": None,
        "right": [], "wrong": [], "cost_pawns": 0.0, "fen_before": chess.STARTING_FEN})
    G.reset()
    yield
    G.configure(max_games=20, idle_seconds=None)
    G.reset()


def test_the_open_server_has_only_game_tools_and_no_way_to_reach_stored_data():
    names = {t.name for t in asyncio.run(S.build_server(public=True).list_tools())}
    assert names == GAME_TOOLS
    assert not any(w in n for n in names for w in ("practice", "progress", "test", "baseline", "assessment"))


def test_the_open_server_never_opens_a_database_or_a_model(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the open server must not touch this")

    monkeypatch.setattr(S, "connect", boom)
    monkeypatch.setattr("app.coach.llm.AnthropicDrafter", boom)
    monkeypatch.setattr(tools, "get_drafter", boom, raising=False)
    server = S.build_server(public=True)
    result = asyncio.run(server.call_tool("game_new", {"color": "black", "level": 2, "mode": "practice"}))
    gid = result.structured_content["game"]["id"]
    for name, args in [("game_hint", {"game_id": gid}), ("game_threats", {"game_id": gid, "show": False}),
                       ("game_show", {"game_id": gid})]:
        assert not asyncio.run(server.call_tool(name, args)).is_error


def test_the_instructions_say_games_are_not_saved():
    ins = S.build_server(public=True).instructions
    assert "never saved" in ins and "practice_" not in ins and "Replay My Mistakes" not in ins


def test_no_login_is_needed_and_a_foreign_host_is_refused():
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    with TestClient(S.build_public_http_app(PUBLIC_URL), base_url=PUBLIC_URL) as c:
        r = c.post("/mcp", json=body, headers=headers)
        assert r.status_code == 200 and "game_new" in r.text and "practice_start" not in r.text
        assert c.get("/healthz").text == "ok"
    with TestClient(S.build_public_http_app(PUBLIC_URL), base_url="https://evil.example.com") as c:
        assert c.post("/mcp", json=body, headers=headers).status_code == 421
        assert c.get("/healthz").status_code == 200  # hosting probes come under any name


def test_a_flood_gets_429_instead_of_reaching_the_engine():
    now = [0.0]
    app = S.PublicGuard(S.build_public_http_app(PUBLIC_URL), {"chess.example.org"}, per_minute=3, clock=lambda: now[0])
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    with TestClient(app, base_url=PUBLIC_URL) as c:
        codes = [c.post("/mcp", json=body, headers=headers).status_code for _ in range(5)]
        assert codes[:3] == [200] * 3 and codes[3:] == [429, 429]
        now[0] += 61
        assert c.post("/mcp", json=body, headers=headers).status_code == 200


def test_idle_games_are_forgotten_and_the_cap_is_per_server(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(G.time, "monotonic", lambda: clock[0])
    G.configure(max_games=3, idle_seconds=60)
    ids = [G.game_new("white", 1, "play")[0]["game"]["id"] for _ in range(3)]
    G.game_new("white", 1, "play")  # a fourth pushes the first out
    assert G.is_refusal(G.game_show(ids[0])[1]) and not G.is_refusal(G.game_show(ids[1])[1])
    clock[0] += 61  # everything untouched since is now idle
    assert G.is_refusal(G.game_show(ids[2])[1])
    assert not G.is_refusal(G.game_new("white", 1, "play")[1])


def test_the_open_server_runs_without_an_access_log(monkeypatch):
    seen = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: seen.update(kw))
    monkeypatch.setenv("MCP_PUBLIC_URL", PUBLIC_URL)
    monkeypatch.setenv("STOCKFISH_PATH", __file__)  # any existing file: the engine is not started
    assert S._run_public() == 0
    assert seen["access_log"] is False


def test_the_privacy_page_is_served_to_anyone_and_matches_the_limits():
    with TestClient(S.build_public_http_app(PUBLIC_URL), base_url=PUBLIC_URL) as c:
        r = c.get("/privacy")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
        for fact in ("No accounts", "2 hours", "500", "does not call any AI model", "Render"):
            assert fact in r.text
        assert "@" not in r.text  # no personal email in a public page
    assert S.PUBLIC_IDLE_SECONDS == 2 * 3600 and S.PUBLIC_MAX_GAMES == 500  # the page states these
