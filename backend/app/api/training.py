"""Training-session endpoints' logic (T44): thin wrappers around the shared `Trainer` with the real engine attached."""

from app.engine.shared import get_engine
from app.engine.stockfish import Budget
from app.learner.training import TRAINER

TRAINER.engine_getter = get_engine
TRAINER.budget = Budget(depth=10)


def start(motif: str) -> dict:
    return TRAINER.start(motif)


def hint(sid: str, index: int, level: int) -> dict:
    return TRAINER.hint(sid, index, level)


def attempt(sid: str, index: int, uci: str) -> dict:
    return TRAINER.attempt(sid, index, uci)


def give_up(sid: str, index: int) -> dict:
    return TRAINER.give_up(sid, index)


def progress() -> dict:
    return TRAINER.progress()
