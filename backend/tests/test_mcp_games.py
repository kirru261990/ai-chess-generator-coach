"""Games against Stockfish as chat tools (ADR 0009): the tool list, rule 4 (no help in Play, in data or text), mode and ownership."""

import asyncio
import json

import chess
import pytest

from app.api import tools
from app.api.store import GAMES
from app.mcp import game_tools as G
from app.mcp import server as S

GAME_TOOLS = {"game_new", "game_show", "game_move", "game_resign", "game_undo", "game_hint", "game_threats"}
GAME_READ_ONLY = {"game_show"}
HELP_KEYS = {"verdict", "headline", "eval", "cp", "mate", "best_move", "better_move", "classification", "badge", "marks", "hint", "hints",
             "hints_used", "threat", "threats", "feedback", "practice", "can_take_back", "assisted", "show_threats", "why"}
HELP_WORDS = ("verdict", "evaluat", "hint", "threat", "blunder", "mistake", "best move", "assisted", "undo")


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
    G.reset()


@pytest.fixture
def server():
    return S.build_server(lambda: None)


def keys_of(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from keys_of(v)
    elif isinstance(x, list):
        for v in x:
            yield from keys_of(v)


def new(mode="play", color="white", level=2):
    d, t = G.game_new(color, level, mode)
    assert d is not None, t
    return d["game"]["id"]


def test_the_game_tools_exist_with_the_right_annotations_and_no_way_to_switch_mode(server):
    tool_list = asyncio.run(server.list_tools())
    names = {t.name for t in tool_list}
    assert GAME_TOOLS <= names
    assert not any("mode" in n or "switch" in n or "test" in n or "baseline" in n for n in names)
    for t in tool_list:
        if t.name in GAME_TOOLS:
            a = t.annotations
            assert a.destructive_hint is False and a.open_world_hint is False
            assert a.read_only_hint is (t.name in GAME_READ_ONLY), t.name
            assert t.description and len(t.description) < 330
            assert t.meta and t.meta["ui"]["resourceUri"] == S.BOARD_URI


def test_the_instructions_keep_the_model_to_relaying_a_play_game(server):
    ins = server.instructions
    for phrase in ("game_", "Play", "never say whether", "game_hint", "not saved"):
        assert phrase in ins


def test_a_play_game_carries_no_help_in_its_data_or_text(server):
    gid = new("play")
    results = [G.game_show(gid)]
    results.append(G.game_move(gid, "e4"))
    results.append(G.game_move(gid, "Nf3"))
    results.append(G.game_resign(gid))
    for d, t in results:
        assert set(d) == {"kind", "game"}
        assert tuple(d["game"]) == G.PLAY_KEYS
        assert not (set(keys_of(d)) & (HELP_KEYS - {"mode"}))
        low = t.lower()
        assert not any(w in low for w in HELP_WORDS), t
        json.dumps(d)  # serialisable as structuredContent


def test_play_through_the_server_returns_structured_content_without_help(server):
    r = asyncio.run(server.call_tool("game_new", {"color": "white", "level": 1, "mode": "play"}))
    sc = r.structured_content
    assert sc["kind"] == "game" and "practice" not in sc and sc["game"]["mode"] == "play"
    gid = sc["game"]["id"]
    r = asyncio.run(server.call_tool("game_move", {"game_id": gid, "move": "e2e4", "expected_revision": 0}))
    assert r.structured_content["game"]["revision"] == 2 and "practice" not in r.structured_content


def test_help_tools_refuse_in_play_and_send_no_data():
    gid = new("play")
    G.game_move(gid, "e4")
    for call in (lambda: G.game_undo(gid), lambda: G.game_hint(gid, 1), lambda: G.game_threats(gid, True)):
        d, t = call()
        assert d is None and G.is_refusal(t) and "Practice" in t
    assert GAMES[gid].moves[0] == "e2e4" and not GAMES[gid].assisted and not GAMES[gid].hints


def test_practice_adds_one_nested_object_with_the_help():
    gid = new("practice")
    d, t = G.game_move(gid, "e4")
    assert set(d) == {"kind", "game", "practice"}
    assert tuple(d["game"]) == G.PLAY_KEYS  # the game part is identical to Play's
    p = d["practice"]
    assert set(p) == set(G.PRACTICE_KEYS) and p["assisted"] is True
    assert p["feedback"]["headline"] == "A fine move" and p["feedback"]["prefix"] == ["e2e4"]
    assert "A fine move" in t
    assert p["threats"] is not None and p["show_threats"] is True


def test_threat_toggle_hint_and_undo_in_practice():
    gid = new("practice")
    G.game_move(gid, "e4")
    d, _ = G.game_threats(gid, False)
    assert d["practice"]["show_threats"] is False and d["practice"]["threats"] is None
    d, t = G.game_hint(gid, 1)
    assert d["practice"]["hint"]["level"] == 1 and d["practice"]["hints_used"] == 1 and "Hint:" in t
    d, _ = G.game_undo(gid)
    assert d["game"]["moves"] == [] and d["practice"]["assisted"] is True and d["practice"]["hint"] is None


def test_san_and_uci_are_both_accepted_and_bad_moves_are_refused_in_words():
    gid = new("play")
    d, _ = G.game_move(gid, "Nf3")
    assert d["game"]["moves"][0] == "g1f3" and len(d["game"]["moves"]) == 2  # the engine replied
    d, t = G.game_move(gid, "e2e5")
    assert d is None and "I could not do that" in t
    d, t = G.game_move(gid, "Qh7")
    assert d is None and "not a legal move" in t
    d, t = G.game_move(gid, "d4", expected_revision=0)  # stale
    assert d is None and "changed" in t


def test_castling_is_accepted_in_both_spellings():
    gid = new("play")
    for m in ("e4", "Nf3", "Be2"):
        assert G.game_move(gid, m)[0] is not None
        # the fake engine always plays its first move in alphabetical order, so keep the board for castling simple
    GAMES[gid].moves[:] = ["e2e4", "e7e5", "g1f3", "b8c6", "f1e2", "g8f6"]
    GAMES[gid].revision += 1
    d, _ = G.game_move(gid, "0-0")
    assert d is not None and "e1g1" in d["game"]["moves"]


def test_black_starts_after_the_engine_has_opened():
    d, t = G.game_new("black", 1, "play")
    assert len(d["game"]["moves"]) == 1 and d["game"]["turn"] == "black" and d["game"]["user_color"] == "black"
    assert "Stockfish opened" in t


def test_resigning_ends_the_game_and_later_moves_are_refused():
    gid = new("play")
    d, _ = G.game_resign(gid)
    assert d["game"]["outcome"]["termination"] == "resignation" and d["game"]["legal_moves"] == []
    d, t = G.game_move(gid, "e4")
    assert d is None and "ended" in t


def test_bad_arguments_are_refused_in_words():
    for args in (("green", 3, "play"), ("white", 11, "play"), ("white", 3, "analysis")):
        d, t = G.game_new(*args)
        assert d is None and G.is_refusal(t)


def test_only_games_started_here_can_be_used():
    foreign = tools.start_game("white", "practice", 1)["id"]  # a web-style game in the same dict
    for call in (G.game_show, G.game_resign, G.game_undo, G.game_hint, lambda g: G.game_move(g, "e4"), G.game_threats):
        d, t = call(foreign)
        assert d is None and "no such game" in t
    assert GAMES[foreign].moves == [] and GAMES[foreign].resigned_by is None
    d, t = G.game_show("nope")
    assert d is None and "no such game" in t
    GAMES.pop(foreign)


def test_the_oldest_chat_game_is_dropped_past_the_limit():
    first = new("play")
    for _ in range(G.MAX_GAMES):
        new("play")
    assert G.game_show(first)[0] is None and first not in GAMES
    assert len(G._OWNED) == G.MAX_GAMES


def test_a_failed_search_never_loses_the_move(monkeypatch):
    def broken(gid, ply):
        raise G.EngineError("engine_not_running", "x")
    monkeypatch.setattr(tools, "move_feedback", broken)
    gid = new("practice")
    d, _ = G.game_move(gid, "e4")
    assert d["game"]["moves"][0] == "e2e4" and d["practice"]["feedback"] is None
