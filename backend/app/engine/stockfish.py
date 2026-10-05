"""Stockfish wrapper (T05). Owns evaluations and lines, never teaching claims.

Every result records the engine version and the search budget so analyses are
reproducible (AGENTS.md rule 6). Scores are normalised to a stated perspective,
and mate scores are kept separate from centipawn scores so they are never
averaged or compared as if they were the same unit.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Self

import chess
import chess.engine

DEFAULT_DEPTH = 14


class EngineError(Exception):
    """Raised with a stable error code in `code`."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Budget:
    """Search limit. Depth gives reproducible results; movetime bounds latency."""

    depth: int | None = DEFAULT_DEPTH
    movetime_ms: int | None = None

    def __post_init__(self):
        if self.depth is None and self.movetime_ms is None:
            raise ValueError("budget needs a depth or a movetime")

    def limit(self) -> chess.engine.Limit:
        t = self.movetime_ms / 1000 if self.movetime_ms is not None else None
        return chess.engine.Limit(depth=self.depth, time=t)


@dataclass(frozen=True)
class Score:
    """Evaluation from one side's point of view.

    Exactly one of `cp` / `mate` is set. `mate` > 0 means this side mates in that
    many moves; `mate` < 0 means this side is mated in that many.
    """

    perspective: chess.Color
    cp: int | None = None
    mate: int | None = None

    @property
    def is_mate(self) -> bool:
        return self.mate is not None


@dataclass(frozen=True)
class Analysis:
    best_move: str | None  # UCI; None when the position has no legal moves
    score: Score
    pv: tuple[str, ...]  # principal variation, UCI
    depth: int
    engine: str  # e.g. "Stockfish 19"
    budget: Budget


def normalise(pov_score: chess.engine.PovScore, perspective: chess.Color) -> Score:
    """Convert an engine score to `perspective`'s point of view."""
    s = pov_score.pov(perspective)
    if s.is_mate():
        return Score(perspective, mate=s.mate())
    return Score(perspective, cp=s.score())


def find_stockfish() -> str:
    path = os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")
    if not path or not os.path.exists(path):
        raise EngineError("engine_not_found", "set STOCKFISH_PATH to a Stockfish binary")
    return path


class Engine:
    """Context manager around one Stockfish process."""

    def __init__(self, path: str | None = None, default_budget: Budget | None = None):
        self._path = path or find_stockfish()
        self.default_budget = default_budget or Budget(
            depth=int(os.environ.get("ENGINE_DEFAULT_DEPTH", DEFAULT_DEPTH))
        )
        self._engine: chess.engine.SimpleEngine | None = None
        self.name = ""

    def __enter__(self) -> Self:
        self._engine = chess.engine.SimpleEngine.popen_uci(self._path)
        self.name = self._engine.id.get("name", "unknown")
        return self

    def __exit__(self, *exc) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def analyse(
        self,
        board: chess.Board,
        budget: Budget | None = None,
        perspective: chess.Color | None = None,
    ) -> Analysis:
        """Analyse `board`. Score is from `perspective` (default: side to move)."""
        if self._engine is None:
            raise EngineError("engine_not_running", "use Engine as a context manager")
        budget = budget or self.default_budget
        perspective = board.turn if perspective is None else perspective
        info = self._engine.analyse(board, budget.limit())
        pv = tuple(m.uci() for m in info.get("pv", []))
        return Analysis(
            best_move=pv[0] if pv else None,
            score=normalise(info["score"], perspective),
            pv=pv,
            depth=info.get("depth", 0),
            engine=self.name,
            budget=budget,
        )
