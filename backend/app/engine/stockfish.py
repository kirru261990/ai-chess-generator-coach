"""Stockfish wrapper (T05). Owns evaluations and lines, never teaching claims.

Every result records the engine version and the search budget so analyses are
reproducible (AGENTS.md rule 6). Scores are normalised to a stated perspective,
and mate scores are kept separate from centipawn scores so they are never
averaged or compared as if they were the same unit.
"""

from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass
from typing import Self

import chess
import chess.engine

DEFAULT_DEPTH = 14
MAX_LEVEL = 10
PLAY_MOVETIME_MS = 200


def skill_for_level(level: int) -> int:
    """Map product "Level 1..10" to Stockfish Skill Level (0, 2, ..., 18).

    Levels are labels for relative strength, not Elo ratings (spec A2).
    """
    if not 1 <= level <= MAX_LEVEL:
        raise ValueError(f"level must be 1..{MAX_LEVEL}")
    return (level - 1) * 2


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

    Exactly one of `cp` / `mate` is set. `mate` is the distance in moves. `mate_sign` says
    who mates: +1 this side delivers mate, -1 this side is mated. They are separate because
    a position that is already checkmate has distance 0 for both sides, so the distance alone
    cannot say who won.
    """

    perspective: chess.Color
    cp: int | None = None
    mate: int | None = None
    mate_sign: int | None = None

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
        distance = s.mate()
        if distance == 0:  # already checkmate: the library keeps the winner in the ordering
            sign = 1 if s > chess.engine.Cp(0) else -1
        else:
            sign = 1 if distance > 0 else -1
        return Score(perspective, mate=distance, mate_sign=sign)
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
        self._lock = threading.Lock()  # one search at a time per process
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
        with self._lock:
            self._engine.configure({"Skill Level": 20})  # analysis is always full strength
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

    def analyse_multi(
        self,
        board: chess.Board,
        multipv: int,
        budget: Budget | None = None,
        perspective: chess.Color | None = None,
    ) -> list[Analysis]:
        """Top `multipv` lines, best first. Used to list acceptable alternatives."""
        if self._engine is None:
            raise EngineError("engine_not_running", "use Engine as a context manager")
        budget = budget or self.default_budget
        perspective = board.turn if perspective is None else perspective
        with self._lock:
            self._engine.configure({"Skill Level": 20})
            infos = self._engine.analyse(board, budget.limit(), multipv=multipv)
        out = []
        for info in infos:
            pv = tuple(m.uci() for m in info.get("pv", []))
            out.append(
                Analysis(
                    best_move=pv[0] if pv else None,
                    score=normalise(info["score"], perspective),
                    pv=pv,
                    depth=info.get("depth", 0),
                    engine=self.name,
                    budget=budget,
                )
            )
        return out

    def play(self, board: chess.Board, level: int, movetime_ms: int = PLAY_MOVETIME_MS) -> str:
        """Pick an opponent move (UCI) at the given product level."""
        if self._engine is None:
            raise EngineError("engine_not_running", "use Engine as a context manager")
        skill = skill_for_level(level)
        with self._lock:
            self._engine.configure({"Skill Level": skill})
            result = self._engine.play(board, chess.engine.Limit(time=movetime_ms / 1000))
        if result.move is None:
            raise EngineError("no_move", "engine returned no move")
        return result.move.uci()
