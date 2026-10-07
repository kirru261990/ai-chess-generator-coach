"""Freeze the baseline window: the fixed set of the owner's games measured before any coaching (T14a).

The window is the N most recent case-study games (10|0 and 15|10) by end time. Its game ids are written to
`data/baseline/` (git-ignored: it holds the owner's games) together with a fingerprint (sha256) of the id list,
overall and per time control. The repository records only the fingerprints and counts, never the ids.
Once written the file is read-only and is never edited (AGENTS.md); `verify` recomputes the fingerprints.

  uv run python -m app.learner.baseline freeze    # write data/baseline/baseline_window_v1.json (refuses to overwrite)
  uv run python -m app.learner.baseline verify    # check the file against its own fingerprints
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

from app import config
from app.engine.batch import game_id

TIME_CONTROLS = {"600": "10|0", "900+10": "15|10"}  # Chess.com time_control -> label
WINDOW_SIZE = 100
RULE = "the 100 most recent case-study games (10|0 and 15|10) by end time"
FILE_NAME = "baseline_window_v1.json"


class BaselineError(Exception):
    pass


def baseline_path() -> Path:
    return config.DATA_DIR / "baseline" / FILE_NAME


def ids_hash(ids) -> str:
    """Order-independent fingerprint of a list of game ids."""
    return hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode()).hexdigest()


def select_window(games: list[dict], n: int = WINDOW_SIZE) -> list[dict]:
    """The n most recent games. Ties on end time are broken by game id so the choice is deterministic."""
    known = [g for g in games if g["time_control"] in TIME_CONTROLS]
    ordered = sorted(known, key=lambda g: (g["end_time"], game_id(g["source_id"])), reverse=True)
    if len(ordered) < n:
        raise BaselineError(f"only {len(ordered)} case-study games available, need {n}")
    return ordered[:n]


def build_record(games: list[dict], n: int = WINDOW_SIZE, now: datetime | None = None) -> dict:
    window = select_window(games, n)
    by_tc = {}
    for code, label in TIME_CONTROLS.items():
        ids = sorted(game_id(g["source_id"]) for g in window if g["time_control"] == code)
        by_tc[label] = {"count": len(ids), "ids": ids, "sha256": ids_hash(ids)}
    ids = sorted(game_id(g["source_id"]) for g in window)
    times = sorted(g["end_time"] for g in window)
    return {
        "version": 1,
        "status": "FROZEN",
        "frozen_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "rule": RULE,
        "n": len(ids),
        "ids": ids,
        "sha256": ids_hash(ids),
        "by_time_control": by_tc,
        "first_game_end_time": times[0],
        "last_game_end_time": times[-1],
        "reporting": "per time control only for now; no pooled figure (owner decision 2026-10-07, reversible)",
    }


def freeze(games: list[dict], path: Path | None = None, n: int = WINDOW_SIZE) -> dict:
    path = path or baseline_path()
    if path.exists():
        raise BaselineError(f"{path} already exists: a frozen baseline is never overwritten")
    record = build_record(games, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1) + "\n")
    os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # read-only
    return record


def verify(path: Path | None = None) -> dict:
    """Recompute every fingerprint from the stored ids; raise if anything differs."""
    path = path or baseline_path()
    record = json.loads(path.read_text())
    problems = []
    if ids_hash(record["ids"]) != record["sha256"]:
        problems.append("overall fingerprint does not match the stored ids")
    for label, part in record["by_time_control"].items():
        if ids_hash(part["ids"]) != part["sha256"]:
            problems.append(f"{label} fingerprint does not match its ids")
        if part["count"] != len(part["ids"]):
            problems.append(f"{label} count does not match its ids")
    union = sorted(i for part in record["by_time_control"].values() for i in part["ids"])
    if union != sorted(record["ids"]):
        problems.append("the per-time-control lists do not add up to the window")
    if problems:
        raise BaselineError("; ".join(problems))
    return record


def _games() -> list[dict]:
    username = config.chesscom_username()
    if not username:
        raise BaselineError("set CHESSCOM_USERNAME in .env")
    path = config.DATA_DIR / "games" / f"chesscom_{username.lower()}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv: list[str]) -> None:
    if not argv or argv[0] not in ("freeze", "verify"):
        sys.exit(__doc__)
    try:
        record = freeze(_games()) if argv[0] == "freeze" else verify()
    except BaselineError as e:
        sys.exit(str(e))
    print(json.dumps({k: record[k] for k in ("status", "frozen_at", "rule", "n", "sha256")}, indent=1))
    for label, part in record["by_time_control"].items():
        print(f"  {label}: {part['count']} games, sha256 {part['sha256']}")


if __name__ == "__main__":
    main(sys.argv[1:])
