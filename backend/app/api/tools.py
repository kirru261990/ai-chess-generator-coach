"""Tool layer shared by the web API and the MCP server (spec §06)."""

import chess

from app.api.store import GAMES
from app.core.game import Game, GameError, Mode, make_move, new_game, resign, to_pgn


def game_view(game: Game) -> dict:
    return {
        "id": game.id,
        "fen": game.fen,
        "moves": list(game.moves),
        "revision": game.revision,
        "turn": "white" if game.board().turn == chess.WHITE else "black",
        "user_color": "white" if game.user_color == chess.WHITE else "black",
        "mode": game.mode.value,
        "assisted": game.assisted,
        "outcome": game.outcome(),
    }


def _get(game_id: str) -> Game:
    game = GAMES.get(game_id)
    if game is None:
        raise GameError("not_found", f"no game {game_id}")
    return game


def start_game(color: str = "white", mode: str = "play") -> dict:
    game = new_game(chess.WHITE if color == "white" else chess.BLACK, Mode(mode))
    GAMES[game.id] = game
    return game_view(game)


def get_game(game_id: str) -> dict:
    return game_view(_get(game_id))


def apply_move(game_id: str, uci: str, expected_revision: int) -> dict:
    return game_view(make_move(_get(game_id), uci, expected_revision))


def resign_game(game_id: str) -> dict:
    game = _get(game_id)
    return game_view(resign(game, game.user_color))


def export_pgn(game_id: str) -> str:
    return to_pgn(_get(game_id))
