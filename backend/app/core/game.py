"""Chess game state. The backend owns legality; nothing here imports an LLM."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import chess
import chess.pgn


class Mode(str, Enum):
    PLAY = "play"
    PRACTICE = "practice"


MAX_TAKEBACKS = 2  # in a row; making a move resets the count


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
    engine_level: int | None = None  # opponent strength; None = no engine opponent
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Counts every state change (move, resignation, takeback). It only ever goes up, so a
    # stale client revision can never match a position that was reached after an undo.
    revision: int = 0
    takebacks_in_row: int = 0  # consecutive takebacks since the last move
    # Every state change validates and mutates under this lock, so two requests can never
    # both pass the same revision check. Reentrant: callers may hold it across several steps.
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    @property
    def takebacks_left(self) -> int:
        if self.mode is not Mode.PRACTICE or self.resigned_by is not None:
            return 0
        return max(0, MAX_TAKEBACKS - self.takebacks_in_row) if self._can_take_back() else 0

    def _plies_to_remove(self) -> int:
        """Back to the user's turn: drop the engine's reply and the user's move, or just the
        user's move if the engine has not replied yet."""
        if self.engine_level is None or self.board().turn != self.user_color:
            return 1
        return 2

    def _can_take_back(self) -> bool:
        return len(self.moves) >= self._plies_to_remove()

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
        board = self.board()
        # Automatic endings only. python-chess' claim_draw=True would also end the game on a
        # *prospective* claim (a repetition that the next move would create), so repetition
        # and the fifty-move rule are checked as they actually stand.
        outcome = board.outcome(claim_draw=False)
        if outcome is not None:
            return {"result": outcome.result(), "termination": outcome.termination.name.lower()}
        if board.is_repetition(3):
            return {"result": "1/2-1/2", "termination": "threefold_repetition"}
        if board.is_fifty_moves():
            return {"result": "1/2-1/2", "termination": "fifty_moves"}
        return None


def new_game(
    user_color: chess.Color = chess.WHITE,
    mode: Mode = Mode.PLAY,
    start_fen: str = chess.STARTING_FEN,
    engine_level: int | None = None,
) -> Game:
    try:
        chess.Board(start_fen)
    except ValueError as e:
        raise GameError("invalid_fen", str(e)) from e
    # Positions start assisted if the game begins in Practice mode.
    return Game(id=uuid.uuid4().hex, user_color=user_color, mode=mode, start_fen=start_fen,
                assisted=mode is Mode.PRACTICE, engine_level=engine_level)


def set_mode(game: Game, mode: Mode) -> None:
    """Switching to Practice mid-game marks the game assisted permanently."""
    with game.lock:
        game.mode = mode
        if mode is Mode.PRACTICE:
            game.assisted = True


def make_move(game: Game, uci: str, expected_revision: int) -> Game:
    with game.lock:
        if expected_revision != game.revision:
            raise GameError("revision_conflict", f"expected {expected_revision}, at {game.revision}")
        if game.outcome() is not None:
            raise GameError("game_over", "game has ended")
        board = game.board()
        try:
            move = board.parse_uci(uci)
        except ValueError as e:
            raise GameError("illegal_move", f"{uci}: {e}") from e
        # parse_uci also accepts the null move "0000", which is not a legal move.
        if move not in board.legal_moves:
            raise GameError("illegal_move", f"{uci}: not a legal move here")
        game.moves.append(move.uci())
        game.takebacks_in_row = 0
        game.revision += 1
        return game


def take_back(game: Game) -> Game:
    """Undo the user's last move (and the engine's reply). Practice mode only, at most
    MAX_TAKEBACKS in a row. The game stays assisted for good."""
    with game.lock:
        if game.mode is not Mode.PRACTICE:
            raise GameError("takeback_not_allowed", "takebacks are only available in Practice mode")
        if game.resigned_by is not None:
            raise GameError("game_over", "game has ended")
        if game.takebacks_in_row >= MAX_TAKEBACKS:
            raise GameError("takeback_limit", f"at most {MAX_TAKEBACKS} takebacks in a row")
        if not game._can_take_back():
            raise GameError("nothing_to_take_back", "no move of yours to take back")
        del game.moves[-game._plies_to_remove() :]
        game.takebacks_in_row += 1
        game.assisted = True
        game.revision += 1
        return game


def resign(game: Game, color: chess.Color) -> Game:
    with game.lock:
        if game.outcome() is not None:
            raise GameError("game_over", "game has ended")
        game.resigned_by = color
        game.revision += 1
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
