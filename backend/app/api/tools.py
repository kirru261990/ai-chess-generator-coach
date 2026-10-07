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
from app.learner.feedback import FEEDBACK_BUDGET, judge


def _color(c: chess.Color) -> str:
    return "white" if c == chess.WHITE else "black"


def _user_legal_moves(game: Game, board: chess.Board) -> list[str]:
    if game.outcome() is not None or board.turn != game.user_color:
        return []
    return [m.uci() for m in board.legal_moves]


def game_view(game: Game) -> dict:
    with game.lock:
        return _game_view(game)


def _game_view(game: Game) -> dict:
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

    Idempotent, so a client can safely retry after a failure. The search runs outside the
    game's lock (it is slow); the move is then applied against the revision captured before
    thinking, so a takeback, resignation or mode change in the meantime rejects the late
    move (revision_conflict) instead of playing it on the wrong position.
    """
    game = _get(game_id)
    with game.lock:
        if not _engine_to_move(game):
            return _game_view(game)
        revision, board, level = game.revision, game.board(), game.engine_level
    uci = get_engine().play(board, level)
    make_move(game, uci, revision)  # validates and applies atomically under the lock
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
    with game.lock:  # the turn check and the move are one step
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


def move_feedback(game_id: str, ply: int) -> dict:
    """What was right or wrong about the user's move at `ply` (0-based index into the game's moves).

    Practice only: feedback is assistance, so Play games are refused (Practice is never assessment, rule 4).
    The search runs outside the lock; the move and position are copied first and returned with the answer, so a
    client can discard feedback for a move that has since been taken back.
    """
    game = _get(game_id)
    with game.lock:
        if game.mode is not Mode.PRACTICE:
            raise GameError("feedback_not_allowed", "move feedback is only available in Practice mode")
        if not 0 <= ply < len(game.moves):
            raise GameError("invalid_ply", f"no move {ply} in this game")
        board = chess.Board(game.start_fen)
        for uci in game.moves[:ply]:
            board.push_uci(uci)
        if board.turn != game.user_color:
            raise GameError("invalid_ply", "that was the opponent's move")
        move = chess.Move.from_uci(game.moves[ply])
        user = game.user_color
    engine = get_engine()
    best = engine.analyse(board, FEEDBACK_BUDGET, perspective=user)
    played_board = board.copy()
    played_board.push(move)
    after = engine.analyse(played_board, FEEDBACK_BUDGET, perspective=user)
    return {"ply": ply, **judge(board, move, best, after)}
