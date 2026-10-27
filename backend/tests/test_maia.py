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


@pytest.mark.parametrize("elo", [399, 2801, 1100.5, "1100", None, True])
def test_a_bad_elo_is_refused(elo):
    with pytest.raises(ValueError):
        maia.check_elo(elo)


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
