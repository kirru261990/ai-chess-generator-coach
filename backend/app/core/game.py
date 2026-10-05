"""Chess game state. The backend owns legality; nothing here imports an LLM."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import chess
import chess.pgn


class Mode(str, Enum):
    PLAY = "play"
    PRACTICE = "practice"


class GameError(Exception):
    """Raised with a stable error code in `code`."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Game:
    id: str
    user_color: chess.Color
    mode: Mode
    start_fen: str = chess.STARTING_FEN
    moves: list[str] = field(default_factory=list)  # UCI, in order
    assisted: bool = False
    resigned_by: chess.Color | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def revision(self) -> int:
        """Increments on every accepted move or resignation."""
        return len(self.moves) + (1 if self.resigned_by is not None else 0)

    def board(self) -> chess.Board:
        board = chess.Board(self.start_fen)
        for uci in self.moves:
            board.push_uci(uci)
        return board

    @property
    def fen(self) -> str:
        return self.board().fen()

    def outcome(self) -> dict | None:
        """Return {result, termination} when the game is over, else None."""
        if self.resigned_by is not None:
            winner = not self.resigned_by
            return {"result": "1-0" if winner == chess.WHITE else "0-1", "termination": "resignation"}
        outcome = self.board().outcome(claim_draw=True)
        if outcome is None:
            return None
        return {"result": outcome.result(), "termination": outcome.termination.name.lower()}


def new_game(
    user_color: chess.Color = chess.WHITE,
    mode: Mode = Mode.PLAY,
    start_fen: str = chess.STARTING_FEN,
) -> Game:
    try:
        chess.Board(start_fen)
    except ValueError as e:
        raise GameError("invalid_fen", str(e)) from e
    # Positions start assisted if the game begins in Practice mode.
    return Game(id=uuid.uuid4().hex, user_color=user_color, mode=mode, start_fen=start_fen,
                assisted=mode is Mode.PRACTICE)


def set_mode(game: Game, mode: Mode) -> None:
    """Switching to Practice mid-game marks the game assisted permanently."""
    game.mode = mode
    if mode is Mode.PRACTICE:
        game.assisted = True


def make_move(game: Game, uci: str, expected_revision: int) -> Game:
    if expected_revision != game.revision:
        raise GameError("revision_conflict", f"expected {expected_revision}, at {game.revision}")
    if game.outcome() is not None:
        raise GameError("game_over", "game has ended")
    board = game.board()
    try:
        move = board.parse_uci(uci)  # raises on illegal / malformed
    except ValueError as e:
        raise GameError("illegal_move", f"{uci}: {e}") from e
    game.moves.append(move.uci())
    return game


def resign(game: Game, color: chess.Color) -> Game:
    if game.outcome() is not None:
        raise GameError("game_over", "game has ended")
    game.resigned_by = color
    return game


def to_pgn(game: Game, white: str = "White", black: str = "Black") -> str:
    pgn_game = chess.pgn.Game()
    if game.start_fen != chess.STARTING_FEN:
        pgn_game.setup(game.start_fen)
    node = pgn_game
    for uci in game.moves:
        node = node.add_variation(chess.Move.from_uci(uci))
    outcome = game.outcome()
    pgn_game.headers.update({
        "Event": "AI Chess Coach",
        "Date": game.created_at.strftime("%Y.%m.%d"),
        "White": white,
        "Black": black,
        "Result": outcome["result"] if outcome else "*",
        "Assisted": str(game.assisted).lower(),
        "Mode": game.mode.value,
    })
    return str(pgn_game)
