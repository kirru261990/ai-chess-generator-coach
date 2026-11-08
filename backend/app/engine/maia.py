"""Maia-3 human-like opponent (T28). Picks moves only; never evaluates, never teaches.

Maia-3 (CSSLab/maia3, code AGPL-3.0) speaks UCI, so it runs as a subprocess the same way Stockfish does and
PyTorch stays out of this project's dependencies. Install it in its own environment (docs/maia-setup.md) and
set `MAIA3_CMD` to it (opt-in: unset or blank means no Maia-3). Without it, `available()` is False and a game asking for Maia-3 is refused: the
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
from pathlib import Path
from typing import Self

import chess
import chess.engine

from app.engine.stockfish import EngineError

DEFAULT_MODEL = "maia3-5m"
# The range we accept is the range we have checked, not a range the model documents (it documents none). The band check of
# 2026-11-08 (evals/tools/maia_band_check.py, ADR 0012) played settings from 500 to 2000: a lower setting plays measurably
# weaker down to 500, and nothing outside 500..2000 was tried.
MIN_ELO, MAX_ELO = 500, 2000
# The Hugging Face snapshot each model alias was checked against (ADR 0012, band check). A game played on any other snapshot is
# recorded as not pinned, never refused: the model is not ours to freeze, but the result of a game must say what played it.
MODEL_REPOS = {"maia3-5m": "UofTCSSLab/Maia3-5M"}
PINNED_CHECKPOINTS = {"maia3-5m": "b6559de2398d7140b985f28fd2c19fb5e47ddabe"}
DEFAULT_TEMPERATURE = 1.0  # sample from the model's move distribution; 0 would always play its top move
START_TIMEOUT_S = 120  # the first start may download weights


def checkpoint(model: str) -> str | None:
    """The Hugging Face snapshot hash of `model`'s weights as cached on this computer, or None if it cannot be found.

    `MAIA3_CHECKPOINT` overrides it (a deployment that knows its snapshot). Otherwise: the cache's `refs/main`, or the only
    snapshot there. Never starts Maia-3 and never downloads anything."""
    forced = os.environ.get("MAIA3_CHECKPOINT", "").strip()
    if forced:
        return forced
    repo = MODEL_REPOS.get(model)
    if repo is None:
        return None
    home = Path(os.environ.get("HF_HUB_CACHE") or Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub")
    folder = home / ("models--" + repo.replace("/", "--"))
    ref = folder / "refs" / "main"
    if ref.is_file():
        return ref.read_text().strip() or None
    snaps = [p.name for p in (folder / "snapshots").glob("*") if p.is_dir()] if (folder / "snapshots").is_dir() else []
    return snaps[0] if len(snaps) == 1 else None


def setup_for(cfg: dict) -> dict:
    """What to record about a Maia-3 process started with `cfg`: model, device, temperature, the checkpoint found on disk and
    whether it is the one that was checked. Never the command line."""
    found = checkpoint(cfg["model"])
    return {
        "model": cfg["model"],
        "device": cfg["device"],
        "temperature": cfg["temperature"],
        "checkpoint": found,
        "checkpoint_pinned": found is not None and found == PINNED_CHECKPOINTS.get(cfg["model"]),
    }


def settings() -> dict:
    """The model setup the environment asks for now (AGENTS.md rule 6). A running process keeps the setup it started with:
    read that from `MaiaOpponent.setup`, never from here."""
    return {
        "cmd": os.environ.get("MAIA3_CMD", "").strip(),  # blank = not configured
        "model": os.environ.get("MAIA3_MODEL", DEFAULT_MODEL),
        "device": os.environ.get("MAIA3_DEVICE", "cpu"),
        "temperature": float(os.environ.get("MAIA3_TEMPERATURE", DEFAULT_TEMPERATURE)),
    }


def command(cfg: dict | None = None) -> list[str]:
    cfg = cfg or settings()
    if not cfg["cmd"]:
        raise EngineError("maia_unavailable", "MAIA3_CMD is not set")
    args = [*shlex.split(cfg["cmd"]), "--model", cfg["model"], "--device", cfg["device"], "--use-uci-history"]
    if cfg["device"] == "cpu":
        args.append("--no-use-amp")
    return args


def available() -> bool:
    try:
        argv = shlex.split(settings()["cmd"])
    except ValueError:  # unbalanced quotes in MAIA3_CMD
        return False
    return bool(argv) and shutil.which(argv[0]) is not None


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
        # What this process was started with, read once the weights are loaded. Games record this, not the environment as it is later.
        self.setup: dict | None = None
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.Lock()

    def __enter__(self) -> Self:
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(command(self.cfg), timeout=START_TIMEOUT_S)
        except (OSError, chess.engine.EngineError, TimeoutError) as e:
            raise EngineError("maia_unavailable", f"could not start Maia-3: {e}") from e
        self.setup = setup_for(self.cfg)
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
