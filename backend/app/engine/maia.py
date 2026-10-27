"""Maia-3 human-like opponent (T28). Picks moves only; never evaluates, never teaches.

Maia-3 (CSSLab/maia3, code AGPL-3.0) speaks UCI, so it runs as a subprocess the same way Stockfish does and
PyTorch stays out of this project's dependencies. Install it in its own environment (docs/maia-setup.md) and
point `MAIA3_CMD` at it. Without it, `available()` is False and a game asking for Maia-3 is refused: the
caller chooses the Stockfish fallback, we never swap the opponent silently (the label must say who was played).

Strength is the Elo the model is conditioned on, not a measured playing strength: label it "Maia-3 at 1100",
never as an Elo claim (spec A2, ADR 0012).
"""

from __future__ import annotations

import atexit
import os
import shlex
import shutil
import threading
from typing import Self

import chess
import chess.engine

from app.engine.stockfish import EngineError

DEFAULT_CMD = "maia3-uci"
DEFAULT_MODEL = "maia3-5m"
# Bounds we accept, not bounds the model supports: the Maia-3 docs do not state its rating range. Narrow these
# once the lowest band has been checked against players under 1000 (spec A2, ADR 0012).
MIN_ELO, MAX_ELO = 400, 2800
DEFAULT_TEMPERATURE = 1.0  # sample from the model's move distribution; 0 would always play its top move
START_TIMEOUT_S = 120  # the first start may download weights


def settings() -> dict:
    """The model setup in force, recorded with every Maia game (AGENTS.md rule 6)."""
    return {
        "cmd": os.environ.get("MAIA3_CMD", DEFAULT_CMD),
        "model": os.environ.get("MAIA3_MODEL", DEFAULT_MODEL),
        "device": os.environ.get("MAIA3_DEVICE", "cpu"),
        "temperature": float(os.environ.get("MAIA3_TEMPERATURE", DEFAULT_TEMPERATURE)),
    }


def command(cfg: dict | None = None) -> list[str]:
    cfg = cfg or settings()
    args = [*shlex.split(cfg["cmd"]), "--model", cfg["model"], "--device", cfg["device"], "--use-uci-history"]
    if cfg["device"] == "cpu":
        args.append("--no-use-amp")
    return args


def available() -> bool:
    return shutil.which(shlex.split(settings()["cmd"])[0]) is not None


def check_elo(elo: int) -> int:
    if isinstance(elo, bool) or not isinstance(elo, int) or not MIN_ELO <= elo <= MAX_ELO:
        raise ValueError(f"elo must be {MIN_ELO}..{MAX_ELO}")
    return elo


def label(elo: int) -> str:
    return f"Maia-3 ({settings()['model']}) at {elo}"


class MaiaOpponent:
    """One long-lived Maia-3 process; moves are serialised by a lock."""

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or settings()
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.Lock()

    def __enter__(self) -> Self:
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(command(self.cfg), timeout=START_TIMEOUT_S)
        except (OSError, chess.engine.EngineError, TimeoutError) as e:
            raise EngineError("maia_unavailable", f"could not start Maia-3: {e}") from e
        return self

    def __exit__(self, *exc) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except (chess.engine.EngineError, TimeoutError):
                self._engine.close()
            self._engine = None

    def play(self, board: chess.Board, elo: int) -> str:
        """A human-like move (UCI) for the side to move, as a player rated `elo` would choose."""
        check_elo(elo)
        if self._engine is None:
            raise EngineError("engine_not_running", "use MaiaOpponent as a context manager")
        with self._lock:
            try:
                self._engine.configure({"Elo": elo, "Temperature": self.cfg["temperature"]})
                result = self._engine.play(board, chess.engine.Limit(nodes=1), game=id(self))
            except (chess.engine.EngineError, TimeoutError) as e:
                raise EngineError("maia_unavailable", f"Maia-3 failed: {e}") from e
        if result.move is None or result.move not in board.legal_moves:
            raise EngineError("no_move", "Maia-3 returned no legal move")
        return result.move.uci()


_lock = threading.Lock()
_maia: MaiaOpponent | None = None


def get_maia() -> MaiaOpponent:
    global _maia
    with _lock:
        if _maia is None:
            _maia = MaiaOpponent().__enter__()
            atexit.register(close_maia)
        return _maia


def close_maia() -> None:
    global _maia
    with _lock:
        if _maia is not None:
            _maia.__exit__(None, None, None)
            _maia = None
