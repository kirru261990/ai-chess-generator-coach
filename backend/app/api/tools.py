"""Tool layer shared by the web API and the MCP server (spec §06)."""

import chess

from app.api.store import GAMES
from app.core.game import (
    Game,
    GameError,
    Mode,
    make_move,
    new_game,
    resign,
    set_mode,
    take_back,
    to_pgn,
)
from app.engine.shared import get_engine
from app.engine.stockfish import MAX_LEVEL


def _color(c: chess.Color) -> str:
    return "white" if c == chess.WHITE else "black"


def _user_legal_moves(game: Game, board: chess.Board) -> list[str]:
    if game.outcome() is not None or board.turn != game.user_color:
        return []
    return [m.uci() for m in board.legal_moves]


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
        "takebacks_left": game.takebacks_left,
        "engine_level": game.engine_level,
        "outcome": game.outcome(),
        # Legal moves for the user, so the client can highlight targets. The server still
        # validates every move; this list is a convenience, never the authority.
        "legal_moves": _user_legal_moves(game, board),
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
        revision = game.revision  # captured before thinking: if the game changes meanwhile
        uci = get_engine().play(game.board(), game.engine_level)  # (e.g. a takeback), the
        make_move(game, uci, revision)  # stale move is rejected instead of played
    return game_view(game)


def start_game(color: str = "white", mode: str = "play", level: int = 3) -> dict:
    if color not in ("white", "black"):
        raise GameError("invalid_color", "color must be white or black")
    if not 1 <= level <= MAX_LEVEL:
        raise GameError("invalid_level", f"level must be 1..{MAX_LEVEL}")
    if mode not in {m.value for m in Mode}:
        raise GameError("invalid_mode", "mode must be play or practice")
    game = new_game(chess.WHITE if color == "white" else chess.BLACK, Mode(mode), engine_level=level)
    GAMES[game.id] = game
    if _engine_to_move(game):  # user chose black: engine opens
        return engine_reply(game.id)
    return game_view(game)


def switch_mode(game_id: str, mode: str) -> dict:
    """Switch Play/Practice. Moving to Practice marks the game assisted permanently."""
    if mode not in {m.value for m in Mode}:
        raise GameError("invalid_mode", "mode must be play or practice")
    game = _get(game_id)
    set_mode(game, Mode(mode))
    return game_view(game)


def get_game(game_id: str) -> dict:
    return game_view(_get(game_id))


def apply_move(game_id: str, uci: str, expected_revision: int, engine_reply_: bool = True) -> dict:
    game = _get(game_id)
    if game.outcome() is None and game.board().turn != game.user_color:
        raise GameError("not_your_turn", "it is the opponent's turn")
    make_move(game, uci, expected_revision)
    return engine_reply(game_id) if engine_reply_ else game_view(game)


def take_back_move(game_id: str) -> dict:
    return game_view(take_back(_get(game_id)))


def resign_game(game_id: str) -> dict:
    game = _get(game_id)
    return game_view(resign(game, game.user_color))


def export_pgn(game_id: str) -> str:
    game = _get(game_id)
    you, opp = "You", f"Stockfish Level {game.engine_level}"
    white, black = (you, opp) if game.user_color == chess.WHITE else (opp, you)
    return to_pgn(game, white=white, black=black)
