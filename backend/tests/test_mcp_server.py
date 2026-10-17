"""The MCP server in-process: the tool list, the annotations, the instructions, and each tool called through the server."""

import asyncio
from contextlib import contextmanager

import pytest

from app.db.schema import connect
from app.mcp import server as S
from tests.test_practice import FakeAnalyser, make_store

GAME_TOOLS = {"game_new", "game_show", "game_move", "game_resign", "game_undo", "game_hint", "game_threats"}  # tests/test_mcp_games.py
EXPECTED = GAME_TOOLS | {"practice_status", "practice_start", "practice_show", "practice_answer", "practice_move", "practice_hint",
            "practice_retry", "practice_next", "practice_summary", "progress"}
READ_ONLY = {"practice_status", "practice_summary", "progress", "game_show"}  # practice_show saves the first attempt of a new session


@contextmanager
def scripted(_conn):
    yield FakeAnalyser()


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "store.sqlite3"
    conn = connect(p)
    make_store(conn)
    conn.close()
    return p


@pytest.fixture
def server(path):
    return S.build_server(lambda: connect(path), scripted)


def call(server, name, **args):
    result = asyncio.run(server.call_tool(name, args))
    assert not result.is_error, result
    return result.content[0].text


def test_only_practice_tools_exist_and_no_test_can_be_reached(server):
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == EXPECTED
    assert not any(w in t.name for t in tools for w in ("test", "baseline", "assessment"))


def test_annotations_say_which_tools_change_data(server):
    for t in asyncio.run(server.list_tools()):
        a = t.annotations
        assert a.destructive_hint is False and a.open_world_hint is False
        assert a.read_only_hint is (t.name in READ_ONLY), t.name
        assert t.description and len(t.description) < 250


def test_the_instructions_tell_the_model_to_only_relay(server):
    ins = server.instructions
    for phrase in ("only relay", "Never analyse", "practice_hint", "exactly", "web app"):
        assert phrase in ins


def test_a_session_through_the_server_with_a_fresh_connection_per_call(server, path):
    status = call(server, "practice_status")
    assert "ready" in status
    text = call(server, "practice_start", mistake_type="pieces_in_danger")
    sid = int(text.split("session ")[1].split()[0])
    assert "Step 1" in call(server, "practice_show", session_id=sid)
    assert "Step 2" in call(server, "practice_answer", session_id=sid, square="a1")
    assert "SOUND" in call(server, "practice_move", session_id=sid, move="Ra2")
    assert "(try 2)" in call(server, "practice_retry", session_id=sid)
    call(server, "practice_answer", session_id=sid, square="a1")
    call(server, "practice_move", session_id=sid, move="Ra2")
    assert "position 2 of 5" in call(server, "practice_next", session_id=sid)
    assert call(server, "practice_summary", session_id=sid).startswith("I could not do that")  # not finished
    assert "Starting test" in call(server, "progress")


def test_a_refusal_comes_back_as_text_not_an_error(server):
    assert call(server, "practice_show", session_id=9999).startswith("I could not do that")
    assert call(server, "practice_start", mistake_type="forks").startswith("I could not do that")


def test_http_mode_refuses_without_a_public_url_or_a_password(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("MCP_PUBLIC_URL", raising=False)
    assert S.main(["http"]) == 2 and "MCP_PUBLIC_URL" in capsys.readouterr().err
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://example.com")  # plain http is only for this machine
    assert S.main(["http"]) == 2 and "MCP_PUBLIC_URL" in capsys.readouterr().err
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://coach.example.com")
    monkeypatch.setattr("app.config.DATA_DIR", tmp_path)
    assert S.main(["http"]) == 2 and "setup" in capsys.readouterr().err
    assert S.main([]) == 2


# --- the interactive board (MCP Apps) -----------------------------------------------------------------------------------

BOARD_TOOLS = EXPECTED - READ_ONLY | {"game_show"}


def test_board_tools_point_at_the_board_and_read_only_tools_do_not(server):
    for t in asyncio.run(server.list_tools()):
        ui = (t.meta or {}).get("ui")
        if t.name in BOARD_TOOLS:
            assert ui and ui["resourceUri"] == S.BOARD_URI, t.name
        else:
            assert not ui, t.name


def test_the_board_is_served_as_an_app_resource(server):
    res = asyncio.run(server.list_resources())
    board = next(r for r in res if str(r.uri) == S.BOARD_URI)
    assert board.mime_type == "text/html;profile=mcp-app"
    body = asyncio.run(server.read_resource(S.BOARD_URI))
    assert "<" in body[0].content  # some HTML (the built board, or the not-built notice)


def test_a_board_tool_returns_the_text_and_the_data_the_board_draws(server):
    result = asyncio.run(server.call_tool("practice_start", {"mistake_type": "pieces_in_danger"}))
    assert not result.is_error and "position 1 of 5" in result.content[0].text
    data = result.structured_content
    assert data["summary"] is None and data["view"]["mistake_type"] == "M1" and data["view"]["total"] == 5
    cur = data["view"]["current"]
    assert cur["stage"] == "recognition" and cur["feedback"] is None  # nothing is revealed before the answer
    again = asyncio.run(server.call_tool("practice_show", {"session_id": data["view"]["session_id"]}))
    assert again.structured_content["view"]["current"]["fen"] == cur["fen"]


def test_a_refusal_has_no_board_data(server):
    result = asyncio.run(server.call_tool("practice_show", {"session_id": 999}))
    assert result.content[0].text.startswith("I could not do that") and not result.structured_content


def test_the_data_for_the_board_matches_the_web_pages(server, path):
    # one source: the same function the web app's API serves
    from app.learner import practice as P
    result = asyncio.run(server.call_tool("practice_start", {"mistake_type": "pieces_in_danger"}))
    sid = result.structured_content["view"]["session_id"]
    conn = connect(path)
    try:
        assert result.structured_content["view"] == P.get_session(conn, sid)
    finally:
        conn.close()
