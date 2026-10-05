"""One long-lived Stockfish process shared by the API (started on first use)."""

import atexit
import threading

from app.engine.stockfish import Engine

_lock = threading.Lock()
_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    with _lock:
        if _engine is None:
            _engine = Engine().__enter__()
            atexit.register(close_engine)
        return _engine


def close_engine() -> None:
    global _engine
    with _lock:
        if _engine is not None:
            _engine.__exit__(None, None, None)
            _engine = None
