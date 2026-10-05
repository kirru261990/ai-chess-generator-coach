"""Tool layer shared by the web API and the MCP server (spec §06)."""

import chess

from app.api.store import GAMES
from app.core.game import Game, GameError, Mode, make_move, new_game, resign, to_pgn
from app.engine.shared import get_engine
from app.engine.stockfish import MAX_LEVEL


def _color(c: chess.Color) -> str:
    return "white" if c == chess.WHITE else "black"


def game_view(game: Game) -> dict:
    board = game.board()
    return {
        "id": game.id,
        "fen": board.fen(),
        "moves": list(game.moves),
        "revision": game.revision,
        "turn": _color(board.turn),
        "user_color": _color(game.user_color),
        "mode": game.mode.value,
        "assisted": game.assisted,
        "engine_level": game.engine_level,
        "outcome": game.outcome(),
    }


def _get(game_id: str) -> Game:
    game = GAMES.get(game_id)
    if game is None:
        raise GameError("not_found", f"no game {game_id}")
    return game


def _engine_to_move(game: Game) -> bool:
    return (
        game.engine_level is not None
        and game.outcome() is None
        and game.board().turn != game.user_color
    )


def engine_reply(game_id: str) -> dict:
    """Play the engine's move if it is the engine's turn; otherwise return state unchanged.

    Idempotent, so a client can safely retry after a failure.
    """
    game = _get(game_id)
    if _engine_to_move(game):
        uci = get_engine().play(game.board(), game.engine_level)
        make_move(game, uci, game.revision)
    return game_view(game)


def start_game(color: str = "white", mode: str = "play", level: int = 3) -> dict:
    if color not in ("white", "black"):
        raise GameError("invalid_color", "color must be white or black")
    if not 1 <= level <= MAX_LEVEL:
        raise GameError("invalid_level", f"level must be 1..{MAX_LEVEL}")
    game = new_game(chess.WHITE if color == "white" else chess.BLACK, Mode(mode), engine_level=level)
    GAMES[game.id] = game
    if _engine_to_move(game):  # user chose black: engine opens
        return engine_reply(game.id)
    return game_view(game)


def get_game(game_id: str) -> dict:
    return game_view(_get(game_id))


def apply_move(game_id: str, uci: str, expected_revision: int, engine_reply_: bool = True) -> dict:
    game = _get(game_id)
    if game.outcome() is None and game.board().turn != game.user_color:
        raise GameError("not_your_turn", "it is the opponent's turn")
    make_move(game, uci, expected_revision)
    return engine_reply(game_id) if engine_reply_ else game_view(game)


def resign_game(game_id: str) -> dict:
    game = _get(game_id)
    return game_view(resign(game, game.user_color))


def export_pgn(game_id: str) -> str:
    game = _get(game_id)
    you, opp = "You", f"Stockfish Level {game.engine_level}"
    white, black = (you, opp) if game.user_color == chess.WHITE else (opp, you)
    return to_pgn(game, white=white, black=black)
