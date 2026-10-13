"""The evidence engine (PRD v2 §4.1, ADR 0006): a pinned Stockfish with a recorded config and a position cache.

Every MISTAKE and CLEAN position, and every sound-move check, uses this config. It is separate from the shallow
searches the live Practice game uses (depth 10 to 16), and its results are never compared with those.

- **Pinned:** the engine must report PINNED_VERSION and PINNED_NETWORK, or `open_evidence` refuses to start. The
  binary's sha256 is recorded too and is part of the config id, so a rebuilt binary is a new config.
- **Recorded:** version, network, binary hash, depth, MultiPV, hash size, threads and score perspective make up an
  `EngineConfig`; its id is a hash of those fields and every cached result and position stores it.
- **Reproducible:** one thread, a fixed hash size, and the hash cleared before each search (`ucinewgame`).
- **Cached:** results are stored by (FEN, config id). A different config never reads another config's results;
  changing any field means re-analysis (PRD §4.1).

Changing the pin or a default here is an ADR-level change: it invalidates every stored position.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import chess

from app.engine.stockfish import Budget, Engine, EngineError

PINNED_VERSION = "Stockfish 19"
PINNED_NETWORK = "nn-1a298aa575a0.nnue"
EVIDENCE_DEPTH = 18
STABILITY_DEPTH_DROP = 4  # PRD §4.5: the loss must also hold at depth - 4
EVIDENCE_MULTIPV = 3
HASH_MB = 64
THREADS = 1


@dataclass(frozen=True)
class EngineConfig:
    version: str
    network: str
    binary_sha256: str
    depth: int
    multipv: int
    hash_mb: int
    threads: int
    score_perspective: str = "white"

    @property
    def id(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True).encode()
        return "ec-" + hashlib.sha256(blob).hexdigest()[:16]

    def at_depth(self, depth: int) -> EngineConfig:
        return replace(self, depth=depth)

    @property
    def stability(self) -> EngineConfig:
        """The same config at depth - 4, for the reliability check."""
        return self.at_depth(self.depth - STABILITY_DEPTH_DROP)


@dataclass(frozen=True)
class Line:
    """One engine line. Scores are from White's point of view; exactly one of cp / mate is set."""

    move: str  # UCI
    pv: tuple[str, ...]
    cp: int | None
    mate: int | None
    mate_sign: int | None  # +1 White mates, -1 Black mates
    depth: int


@dataclass(frozen=True)
class EvidenceAnalysis:
    fen: str
    config_id: str
    lines: tuple[Line, ...]  # best first; empty when the position has no legal moves

    @property
    def best(self) -> Line | None:
        return self.lines[0] if self.lines else None


def binary_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_pin(version: str, network: str | None) -> None:
    if version != PINNED_VERSION or network != PINNED_NETWORK:
        raise EngineError(
            "engine_not_pinned",
            f"evidence needs {PINNED_VERSION} with {PINNED_NETWORK}; found {version} with {network}",
        )


class EvidenceAnalyser:
    """Analyses positions with one fixed config, reading and writing the position cache."""

    def __init__(self, engine, config: EngineConfig, conn: sqlite3.Connection):
        if engine.name != config.version:
            raise EngineError("engine_config_mismatch", f"engine is {engine.name}, config says {config.version}")
        self.engine = engine
        self.config = config
        self.conn = conn
        for cfg in (config, config.stability):
            register_config(conn, cfg)

    def analyse(self, board: chess.Board, depth: int | None = None) -> EvidenceAnalysis:
        """Top lines for `board` at the evidence depth (or `depth`, e.g. the stability depth). Cached."""
        cfg = self.config if depth is None else self.config.at_depth(depth)
        if depth is not None:
            register_config(self.conn, cfg)
        fen = board.fen()
        cached = cached_analysis(self.conn, fen, cfg.id)
        if cached is not None:
            return cached
        if not any(board.legal_moves):  # checkmate or stalemate: nothing to search
            lines: tuple[Line, ...] = ()
        else:
            results = self.engine.analyse_multi(
                board, cfg.multipv, Budget(depth=cfg.depth), perspective=chess.WHITE, new_game=True
            )
            lines = tuple(
                Line(r.best_move, r.pv, r.score.cp, r.score.mate, r.score.mate_sign, r.depth)
                for r in results
                if r.best_move is not None
            )
        result = EvidenceAnalysis(fen, cfg.id, lines)
        store_analysis(self.conn, result)
        return result


def register_config(conn: sqlite3.Connection, cfg: EngineConfig) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO engine_config (id, version, network, binary_sha256, depth, multipv, hash_mb,"
        " threads, score_perspective, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (cfg.id, cfg.version, cfg.network, cfg.binary_sha256, cfg.depth, cfg.multipv, cfg.hash_mb,
         cfg.threads, cfg.score_perspective, _now()),
    )


def cached_analysis(conn: sqlite3.Connection, fen: str, config_id: str) -> EvidenceAnalysis | None:
    row = conn.execute(
        "SELECT lines_json FROM engine_analysis WHERE fen = ? AND engine_config_id = ?", (fen, config_id)
    ).fetchone()
    if row is None:
        return None
    lines = tuple(Line(**{**d, "pv": tuple(d["pv"])}) for d in json.loads(row["lines_json"]))
    return EvidenceAnalysis(fen, config_id, lines)


def store_analysis(conn: sqlite3.Connection, a: EvidenceAnalysis) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO engine_analysis (fen, engine_config_id, lines_json, analysed_at)"
        " VALUES (?, ?, ?, ?)",
        (a.fen, a.config_id, json.dumps([asdict(line) for line in a.lines]), _now()),
    )


@contextmanager
def open_evidence(conn: sqlite3.Connection, path: str | None = None) -> Iterator[EvidenceAnalyser]:
    """Start a dedicated, pinned Stockfish with the evidence settings. Refuses an unpinned build."""
    with Engine(path, options={"Hash": HASH_MB, "Threads": THREADS}) as engine:
        network = engine.option_default("EvalFile")
        check_pin(engine.name, network if isinstance(network, str) else None)
        cfg = EngineConfig(
            version=engine.name,
            network=str(network),
            binary_sha256=binary_sha256(engine.path),
            depth=EVIDENCE_DEPTH,
            multipv=EVIDENCE_MULTIPV,
            hash_mb=HASH_MB,
            threads=THREADS,
        )
        yield EvidenceAnalyser(engine, cfg, conn)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
