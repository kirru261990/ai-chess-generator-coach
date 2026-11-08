import json
import sys
import textwrap

import chess
import pytest

from app.api import tools
from app.core.game import GameError
from app.engine import maia
from app.engine.stockfish import EngineError

# A stand-in for maia3-uci: speaks enough UCI, records the options it was given, plays the first legal move.
FAKE = textwrap.dedent(
    """
    import json, sys, chess
    log, board = sys.argv[1], chess.Board()
    opts = {}
    for line in sys.stdin:
        w = line.split()
        if not w:
            continue
        if w[0] == "uci":
            print("option name Elo type spin default 1500 min 400 max 2800")
            print("option name Temperature type string default 0")
            print("uciok")
        elif w[0] == "isready":
            print("readyok")
        elif w[0] == "setoption":
            opts[w[2]] = w[4]
        elif w[0] == "position":
            board = chess.Board() if w[1] == "startpos" else chess.Board(" ".join(w[2:8]))
            if "moves" in w:
                for m in w[w.index("moves") + 1:]:
                    board.push_uci(m)
        elif w[0] == "go":
            json.dump({"opts": opts, "plies": len(board.move_stack), "argv": sys.argv[2:]}, open(log, "w"))
            print("bestmove " + sorted(m.uci() for m in board.legal_moves)[0])
        elif w[0] == "quit":
            break
        sys.stdout.flush()
    """
)


@pytest.fixture
def fake_maia(tmp_path, monkeypatch):
    script, log = tmp_path / "fake_maia.py", tmp_path / "log.json"
    script.write_text(FAKE)
    monkeypatch.setenv("MAIA3_CMD", f"{sys.executable} {script} {log}")
    monkeypatch.setenv("MAIA3_MODEL", "maia3-5m")
    monkeypatch.setattr(maia, "_maia", None)
    yield log
    maia.close_maia()


def test_a_maia_move_is_legal_and_gets_the_elo_model_and_history(fake_maia):
    board = chess.Board()
    board.push_uci("e2e4")
    with maia.MaiaOpponent() as m:
        uci = m.play(board, 1100)
    assert chess.Move.from_uci(uci) in board.legal_moves
    seen = json.loads(fake_maia.read_text())
    assert seen["opts"]["Elo"] == "1100"
    assert seen["plies"] == 1  # the move list is sent, not just the position
    assert seen["argv"][:2] == ["--model", "maia3-5m"]
    assert "--use-uci-history" in seen["argv"] and "--no-use-amp" in seen["argv"]


@pytest.mark.parametrize("elo", [499, 2001, 1100.5, "1100", None, True])
def test_a_bad_elo_is_refused(elo):
    with pytest.raises(ValueError):
        maia.check_elo(elo)


@pytest.mark.parametrize("elo", [500, 900, 2000])
def test_the_checked_range_is_accepted(elo):
    assert maia.check_elo(elo) == elo


def test_the_checkpoint_comes_from_the_hugging_face_cache(tmp_path, monkeypatch):
    hub = tmp_path / "hub"
    folder = hub / "models--UofTCSSLab--Maia3-5M"
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    monkeypatch.delenv("MAIA3_CHECKPOINT", raising=False)
    assert maia.checkpoint("maia3-5m") is None  # nothing cached yet
    (folder / "snapshots" / "aaa").mkdir(parents=True)
    assert maia.checkpoint("maia3-5m") == "aaa"  # the only snapshot
    (folder / "snapshots" / "bbb").mkdir()
    assert maia.checkpoint("maia3-5m") is None  # two snapshots and no ref: we do not guess
    (folder / "refs").mkdir()
    (folder / "refs" / "main").write_text("bbb\n")
    assert maia.checkpoint("maia3-5m") == "bbb"
    assert maia.checkpoint("maia3-unknown") is None  # an alias we do not know


def test_a_checkpoint_is_pinned_only_when_it_is_the_one_that_was_checked(monkeypatch):
    monkeypatch.setenv("MAIA3_MODEL", "maia3-5m")
    monkeypatch.setenv("MAIA3_CHECKPOINT", maia.PINNED_CHECKPOINTS["maia3-5m"])
    assert maia.setup_for(maia.settings())["checkpoint_pinned"] is True
    monkeypatch.setenv("MAIA3_CHECKPOINT", "some-other-snapshot")
    assert maia.setup_for(maia.settings())["checkpoint_pinned"] is False
    assert maia.setup_for(maia.settings())["checkpoint"] == "some-other-snapshot"


def test_a_maia_game_records_what_played_it_and_never_the_command_line(fake_maia, monkeypatch):
    monkeypatch.setenv("MAIA3_CHECKPOINT", "some-other-snapshot")
    view = tools.start_game("black", "play", opponent="maia3", elo=900)  # Maia opens, so the process has played
    setup = view["opponent_setup"]
    assert {k: setup[k] for k in ("model", "device", "temperature", "checkpoint", "checkpoint_source", "checkpoint_pinned")} == {
        "model": "maia3-5m", "device": "cpu", "temperature": 1.0,
        "checkpoint": "some-other-snapshot", "checkpoint_source": "override", "checkpoint_pinned": False}
    assert setup["process"] and "cmd" not in setup
    assert tools.game_view(tools.create_game())["opponent_setup"] is None  # a Stockfish game records none
    waiting = tools.start_game("white", "play", opponent="maia3", elo=900)  # White moves first: Maia has not played yet
    assert waiting["opponent_setup"] is None


def test_a_late_move_that_is_rejected_records_no_setup(fake_maia, monkeypatch):
    game = tools.create_game("black", "play", opponent="maia3", elo=900)  # Maia is to move, and has not moved
    def conflict(*_a, **_k):
        raise GameError("revision_conflict", "the position changed while Maia-3 was thinking")
    monkeypatch.setattr(tools, "make_move", conflict)
    with pytest.raises(GameError):
        tools.engine_reply(game.id)
    assert game.opponent_setup is None and game.moves == []  # Maia never moved in this game


def test_a_restart_of_maia_during_a_game_is_marked_not_hidden(fake_maia):
    view = tools.start_game("black", "play", opponent="maia3", elo=900)
    first = view["opponent_setup"]
    assert "setup_changed" not in first
    maia.close_maia()  # the next move comes from a new Maia-3 process
    reply = tools.apply_move(view["id"], view["legal_moves"][0], view["revision"])
    second = reply["opponent_setup"]
    assert second["process"] == first["process"] and second["setup_changed"] is True  # the first record is kept, and flagged


def test_the_pgn_names_the_setup_that_played_a_maia_game(fake_maia, monkeypatch):
    monkeypatch.setenv("MAIA3_CHECKPOINT", maia.PINNED_CHECKPOINTS["maia3-5m"])
    view = tools.start_game("black", "play", opponent="maia3", elo=900)
    pgn = tools.export_pgn(view["id"])
    assert '[OpponentSetup "maia3-5m; cpu; temperature 1.0; checkpoint ' + maia.PINNED_CHECKPOINTS["maia3-5m"] in pgn
    assert "the checked snapshot" in pgn
    assert "OpponentSetup" not in tools.export_pgn(tools.start_game("white", "play")["id"])  # a Stockfish game has none


def test_a_chat_game_against_maia_carries_the_setup_once_maia_has_played(fake_maia):
    from app.mcp import game_tools

    data, _text = game_tools.game_new("black", 3, "play", "maia3", 900)
    assert data["game"]["opponent_setup"]["model"] == "maia3-5m"


def test_a_game_records_the_setup_of_the_process_that_plays_it_not_the_cache_as_it_is_later(fake_maia, tmp_path, monkeypatch):
    hub = tmp_path / "hub"
    refs = hub / "models--UofTCSSLab--Maia3-5M" / "refs"
    refs.mkdir(parents=True)
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    monkeypatch.delenv("MAIA3_CHECKPOINT", raising=False)
    monkeypatch.setenv("MAIA3_TEMPERATURE", "1.0")
    (refs / "main").write_text("old-snapshot\n")
    first = tools.start_game("black", "play", opponent="maia3", elo=900)
    # the cache moves on to the checked snapshot and the temperature setting changes, but the same process is still running
    (refs / "main").write_text(maia.PINNED_CHECKPOINTS["maia3-5m"] + "\n")
    monkeypatch.setenv("MAIA3_TEMPERATURE", "0.25")
    second = tools.start_game("black", "play", opponent="maia3", elo=900)
    for view in (first, second):
        assert view["opponent_setup"]["checkpoint"] == "old-snapshot"
        assert view["opponent_setup"]["checkpoint_source"] == "hf_cache"
        assert view["opponent_setup"]["checkpoint_pinned"] is False
        assert view["opponent_setup"]["temperature"] == 1.0


def test_a_missing_maia_command_is_a_clear_engine_error(monkeypatch):
    monkeypatch.setenv("MAIA3_CMD", "definitely-not-installed-maia")
    assert not maia.available()
    with pytest.raises(EngineError) as e:
        maia.MaiaOpponent().__enter__()
    assert e.value.code == "maia_unavailable"


def test_a_maia_game_is_refused_when_maia_is_not_installed(monkeypatch):
    monkeypatch.setenv("MAIA3_CMD", "definitely-not-installed-maia")
    with pytest.raises(GameError) as e:
        tools.create_game("white", "play", opponent="maia3", elo=1000)
    assert e.value.code == "opponent_unavailable"  # never a silent Stockfish swap


def test_opponent_and_elo_are_validated():
    with pytest.raises(GameError) as e:
        tools.create_game(opponent="gpt")
    assert e.value.code == "invalid_opponent"
    with pytest.raises(GameError) as e:
        tools.create_game(opponent="maia3", elo=50)
    assert e.value.code == "invalid_elo"


def test_a_maia_game_plays_the_engine_reply_with_maia_and_labels_the_pgn(fake_maia):
    view = tools.start_game("black", "play", opponent="maia3", elo=900)  # user is black: Maia opens
    assert view["opponent"] == "maia3" and view["opponent_elo"] == 900 and view["engine_level"] is None
    assert len(view["moves"]) == 1
    assert "Maia-3 (maia3-5m) at 900" in tools.export_pgn(view["id"])


def test_takeback_in_a_maia_practice_game_removes_both_plies(fake_maia):
    view = tools.start_game("white", "practice", opponent="maia3", elo=900)
    reply = tools.apply_move(view["id"], "e2e4", view["revision"])
    assert len(reply["moves"]) == 2
    assert len(tools.take_back_move(view["id"])["moves"]) == 0


def test_stockfish_games_are_unchanged_by_default():
    game = tools.create_game()
    assert game.engine_level == 3 and game.opponent_elo is None
    assert tools.game_view(game)["opponent"] == "stockfish"


def test_opponents_endpoint_reports_availability(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.main import app

    monkeypatch.setenv("MAIA3_CMD", "definitely-not-installed-maia")
    assert TestClient(app).get("/opponents").json()["maia3"]["available"] is False


def test_the_chat_game_text_names_a_maia_opponent(fake_maia):
    from app.mcp import game_tools

    _, text = game_tools.game_new("white", 3, "play", "maia3", 900)
    assert "Maia-3 at 900" in text and "Stockfish" not in text

@pytest.mark.parametrize("value", ["", "   ", "'unbalanced"])
def test_a_blank_or_broken_maia_command_means_unavailable_not_a_crash(monkeypatch, value):
    monkeypatch.setenv("MAIA3_CMD", value)
    assert maia.available() is False
    with pytest.raises(GameError) as e:
        tools.create_game(opponent="maia3", elo=900)
    assert e.value.code == "opponent_unavailable"


def test_maia_is_off_when_the_command_is_not_set_at_all(monkeypatch):
    monkeypatch.delenv("MAIA3_CMD", raising=False)
    assert maia.available() is False


def test_chat_notes_name_the_maia_opponent_when_it_opens_replies_or_fails(fake_maia, monkeypatch):
    from app.mcp import game_tools

    _, text = game_tools.game_new("black", 3, "play", "maia3", 900)  # Maia opens
    assert "Maia-3 at 900" in text and "Maia-3 opened with" in text and "Stockfish" not in text
    gid = next(iter(game_tools._OWNED))
    move = min(tools.get_game(gid)["legal_moves"])
    _, text = game_tools.game_move(gid, move)
    assert "Maia-3 replied" in text and "Stockfish" not in text

    def down(*a):
        raise EngineError("maia_unavailable", "gone")

    monkeypatch.setattr(maia.MaiaOpponent, "play", down)
    move = min(tools.get_game(gid)["legal_moves"])
    _, text = game_tools.game_move(gid, move)
    assert "Maia-3 did not answer" in text and "Stockfish" not in text


def test_the_shipped_board_page_can_name_a_maia_opponent():
    """server.py serves the committed board.html, not the TSX: rebuild it (pnpm build:mcp) after changing GameBoard.tsx."""
    from pathlib import Path

    import app.mcp

    page = (Path(app.mcp.__file__).parent / "ui" / "board.html").read_text()
    assert "Maia-3 at " in page
