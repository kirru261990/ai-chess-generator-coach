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


def test_a_mode_change_bumps_the_revision_and_a_no_op_does_not():
    gid = client.post("/games", json={}).json()["id"]
    to_practice = client.post(f"/games/{gid}/mode", json={"mode": "practice"}).json()
    assert to_practice["revision"] == 1 and to_practice["assisted"] is True
    again = client.post(f"/games/{gid}/mode", json={"mode": "practice"}).json()
    assert again["revision"] == 1  # nothing changed
    back = client.post(f"/games/{gid}/mode", json={"mode": "play"}).json()
    assert back["revision"] == 2 and back["assisted"] is True  # assisted never reverts


def test_mode_switch_rejects_bad_input():
    gid = client.post("/games", json={}).json()["id"]
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


def test_legal_moves_are_listed_only_on_the_users_turn():
    g = client.post("/games", json={}).json()
    assert len(g["legal_moves"]) == 20 and "e2e4" in g["legal_moves"]
    pending = move(g["id"], "e2e4", 0, engine_reply=False).json()
    assert pending["legal_moves"] == []  # the opponent's turn
    over = client.post(f"/games/{g['id']}/resign").json()
    assert over["legal_moves"] == []


def test_takeback_api_flow_and_errors():
    gid = client.post("/games", json={"mode": "practice"}).json()["id"]
    r = move(gid, "e2e4", 0, engine_reply=False).json()
    assert r["takebacks_left"] == 2
    back = client.post(f"/games/{gid}/takeback").json()
    assert back["moves"] == [] and back["takebacks_left"] == 0 and back["revision"] > r["revision"]
    assert move(gid, "e2e4", r["revision"], engine_reply=False).json()["error"] == "revision_conflict"
    play_gid = client.post("/games", json={"mode": "play"}).json()["id"]
    err = client.post(f"/games/{play_gid}/takeback")
    assert err.status_code == 409 and err.json()["error"] == "takeback_not_allowed"
    assert client.post(f"/games/{gid}/takeback").json()["error"] == "nothing_to_take_back"


def test_a_late_engine_move_after_a_takeback_is_rejected(monkeypatch):
    class SlowEngine:
        def play(self, board, level):
            tools_take_back(gid)  # the user undoes while the engine is still "thinking"
            return "e7e5"

    gid = client.post("/games", json={"mode": "practice"}).json()["id"]
    move(gid, "e2e4", 0, engine_reply=False)
    monkeypatch.setattr(tools, "get_engine", lambda: SlowEngine())
    tools_take_back = tools.take_back_move
    r = client.post(f"/games/{gid}/engine-move")
    assert r.status_code == 409 and r.json()["error"] == "revision_conflict"
    assert client.get(f"/games/{gid}").json()["moves"] == []  # nothing was applied


def test_null_move_over_http_is_a_400_and_changes_nothing():
    gid = client.post("/games", json={}).json()["id"]
    r = move(gid, "0000", 0, engine_reply=False)
    assert r.status_code == 400 and r.json()["error"] == "illegal_move"
    g = client.get(f"/games/{gid}").json()
    assert g["moves"] == [] and g["turn"] == "white" and g["revision"] == 0


def test_a_late_engine_move_after_a_resignation_is_rejected(monkeypatch):
    class SlowEngine:
        def play(self, board, level):
            tools.resign_game(gid)  # the user resigns while the engine is still "thinking"
            return "e7e5"

    gid = client.post("/games", json={}).json()["id"]
    move(gid, "e2e4", 0, engine_reply=False)
    monkeypatch.setattr(tools, "get_engine", lambda: SlowEngine())
    r = client.post(f"/games/{gid}/engine-move")
    assert r.status_code == 409 and r.json()["error"] == "revision_conflict"
    final = client.get(f"/games/{gid}").json()
    assert final["outcome"] == {"result": "0-1", "termination": "resignation"}
    assert final["moves"] == ["e2e4"]


def test_blind_spots_endpoint_serves_frozen_results_and_refuses_a_foreign_window(tmp_path, monkeypatch):
    import json

    from app import config
    from app.api import blind_spots
    from app.learner import baseline

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    assert client.get("/blind-spots/baseline").status_code == 404  # not frozen yet
    (tmp_path / "baseline").mkdir()
    window = {"sha256": "w1"}
    monkeypatch.setattr(baseline, "verify", lambda: window)
    f = tmp_path / "baseline" / blind_spots.FROZEN_NAME
    f.write_text(json.dumps({"window_sha256": "w1", "by_time_control": {}}))
    r = client.get("/blind-spots/baseline")
    assert r.status_code == 200 and len(r.json()["results_sha256"]) == 64
    f.write_text(json.dumps({"window_sha256": "other", "by_time_control": {}}))
    assert client.get("/blind-spots/baseline").status_code == 500
def test_feedback_is_refused_in_play_mode_and_for_bad_plies():
    gid = client.post("/games", json={"mode": "play"}).json()["id"]
    move(gid, "e2e4", 0, engine_reply=False)
    r = client.get(f"/games/{gid}/feedback/0")
    assert r.status_code == 403 and r.json()["error"] == "feedback_not_allowed"
    client.post(f"/games/{gid}/mode", json={"mode": "practice"})
    assert client.get(f"/games/{gid}/feedback/5").json()["error"] == "invalid_ply"
    assert client.get("/games/nope/feedback/0").status_code == 404


@needs_engine
def test_feedback_for_a_practice_move():
    gid = client.post("/games", json={"mode": "practice", "level": 1}).json()["id"]
    r = move(gid, "f2f3", 0, engine_reply=False).json()
    fb = client.get(f"/games/{gid}/feedback/0")
    assert fb.status_code == 200
    body = fb.json()
    assert body["ply"] == 0 and body["played"]["uci"] == "f2f3"
    assert body["verdict"] in {"good", "slip", "mistake", "blunder"} and body["better_move"]["uci"]
    # the opponent's reply is not judged
    move(gid, "e2e4", r["revision"], engine_reply=False)
    assert client.get(f"/games/{gid}/feedback/1").json()["error"] == "invalid_ply"


def test_coach_why_is_practice_only_and_falls_back_without_a_model(monkeypatch):
    from app.api import tools
    from app.coach.llm import CoachUnavailable

    class NoModel:
        model = "none"

        def draft(self, system, messages):
            raise CoachUnavailable("no key")

    monkeypatch.setattr(tools, "get_drafter", lambda *a: NoModel())
    gid = client.post("/games", json={"mode": "play"}).json()["id"]
    move(gid, "e2e4", 0, engine_reply=False)
    assert client.post(f"/games/{gid}/coach/why", json={"ply": 0}).status_code == 403
    client.post(f"/games/{gid}/mode", json={"mode": "practice"})
    assert client.post(f"/games/{gid}/coach/why", json={"ply": 9}).json()["error"] == "invalid_ply"
    assert client.post("/games/nope/coach/why", json={"ply": 0}).status_code == 404


@needs_engine
def test_coach_why_returns_checked_facts_when_the_model_is_unavailable(monkeypatch):
    from app.api import tools
    from app.coach.llm import CoachUnavailable

    class NoModel:
        model = "none"

        def draft(self, system, messages):
            raise CoachUnavailable("no key")

    monkeypatch.setattr(tools, "get_drafter", lambda *a: NoModel())
    gid = client.post("/games", json={"mode": "practice", "level": 1}).json()["id"]
    move(gid, "f2f3", 0, engine_reply=False)
    r = client.post(f"/games/{gid}/coach/why", json={"ply": 0}).json()
    assert r["status"] == "unavailable" and r["ply"] == 0 and r["played_uci"] == "f2f3" and r["text"]


def _fake_synced(monkeypatch, tmp_path, user_color="white"):
    from app import config
    from app.api import synced
    from app.engine.batch import SCHEMA

    FREE_KNIGHT = "4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1"
    game = {"source_id": "https://www.chess.com/game/live/777", "user_color": user_color}
    analysis = {"schema": SCHEMA, "moves": ["e1f1"], "positions": [{"fen": FREE_KNIGHT}, {"fen": "x"}]}

    class Games:
        def all(self):
            return [game]

    class Analyses:
        def get(self, sid):
            return analysis

    from app.engine.stockfish import Analysis, Budget, Score

    class QuietEngine:  # no mates anywhere: keeps these tests independent of Stockfish
        def analyse(self, board, budget=None, perspective=None):
            return Analysis(None, Score(board.turn if perspective is None else perspective, cp=0), (), 1, "fake", Budget(depth=1))

    monkeypatch.setattr(synced, "_stores", lambda: (Games(), Analyses()))
    monkeypatch.setattr(synced, "get_engine", lambda: QuietEngine())
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)


def test_intent_endpoint_stores_the_answer_as_self_reported_and_builds_gaps_from_facts(monkeypatch, tmp_path):
    import json

    from app.api import tools
    from app.coach.llm import Draft

    class Model:
        model = "fake"

        def draft(self, system, messages):
            return Draft('{"mentioned": []}', "fake")

    _fake_synced(monkeypatch, tmp_path)
    monkeypatch.setattr(tools, "get_drafter", lambda *a: Model())
    r = client.post("/synced-games/777/moments/0/intent", json={"text": "I wanted to castle"}).json()
    assert r["status"] == "compared" and r["self_reported"] is True
    assert r["gaps"] == ["A free knight on d5 was there to take."]
    saved = [json.loads(x) for x in (tmp_path / "intents" / "intents_v1.jsonl").read_text().splitlines()]
    assert saved[0]["answer"] == "I wanted to castle" and saved[0]["self_reported"] is True
    # skipping stores nothing
    r = client.post("/synced-games/777/moments/0/intent", json={}).json()
    assert r["status"] == "skipped" and len((tmp_path / "intents" / "intents_v1.jsonl").read_text().splitlines()) == 1


def test_intent_endpoint_rejects_moves_that_are_not_the_players(monkeypatch, tmp_path):
    _fake_synced(monkeypatch, tmp_path, user_color="black")
    r = client.post("/synced-games/777/moments/0/intent", json={"text": "x"})
    assert r.status_code == 400 and r.json()["error"] == "invalid_ply"
    assert client.post("/synced-games/nope/moments/0/intent", json={}).status_code == 404


@needs_engine
def test_intent_facts_include_an_allowed_mate_found_by_the_engine(monkeypatch, tmp_path):
    import chess

    from app.api import synced, tools
    from app.coach.llm import Draft
    from app.engine.batch import SCHEMA

    board = chess.Board()
    board.push_san("f3")
    board.push_san("e5")  # White to move; 2.g4 allows Qh4#
    game = {"source_id": "https://www.chess.com/game/live/888", "user_color": "white"}
    analysis = {"schema": SCHEMA, "moves": ["f2f3", "e7e5", "g2g4"],
                "positions": [{"fen": "x"}, {"fen": "x"}, {"fen": board.fen()}, {"fen": "x"}]}

    class Games:
        def all(self):
            return [game]

    class Analyses:
        def get(self, sid):
            return analysis

    class Model:
        model = "fake"

        def draft(self, system, messages):
            return Draft('{"mentioned": []}', "fake")

    from app import config

    monkeypatch.setattr(synced, "_stores", lambda: (Games(), Analyses()))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(tools, "get_drafter", lambda *a: Model())
    r = client.post("/synced-games/888/moments/2/intent", json={"text": "attack"}).json()
    assert r["status"] == "compared"
    assert "Your move allowed a forced checkmate against you." in r["gaps"]


def test_eval_is_practice_only_and_404_for_unknown_games():
    gid = client.post("/games", json={"mode": "play"}).json()["id"]
    r = client.get(f"/games/{gid}/eval")
    assert r.status_code == 403 and r.json()["error"] == "feedback_not_allowed"
    assert client.get("/games/nope/eval").status_code == 404


@needs_engine
def test_eval_of_a_practice_position_comes_from_whites_side():
    gid = client.post("/games", json={"mode": "practice", "level": 1}).json()["id"]
    r = client.get(f"/games/{gid}/eval").json()
    assert r["revision"] == 0 and r["mate"] is None and -100 < r["cp"] < 100  # the start is about equal
    # after 1.f3 e5 2.g4 Black mates in one: White's view is mate with mate_sign -1
    rev = 0
    for uci in ("f2f3", "e7e5", "g2g4"):
        v = client.post(f"/games/{gid}/moves", json={"uci": uci, "expected_revision": rev, "engine_reply": False}).json() \
            if uci != "e7e5" else None
        if v:
            rev = v["revision"]
        else:  # the engine's side: the opponent's move is made through the core to keep this test deterministic
            from app.api.store import GAMES
            from app.core.game import make_move

            make_move(GAMES[gid], uci, rev)
            rev += 1
    last = client.get(f"/games/{gid}/eval").json()
    assert last["mate"] is not None and last["mate_sign"] == -1
