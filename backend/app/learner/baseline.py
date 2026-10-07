"""Freeze the baseline window: the fixed set of the owner's games measured before any coaching (T14a).

The window is the N most recent case-study games (10|0 and 15|10) by end time. Its game ids are written to
`data/baseline/` (git-ignored: it holds the owner's games) together with a fingerprint (sha256) of the id list,
overall and per time control. The repository records only the fingerprints and counts, never the ids.
Once written the file is read-only and is never edited (AGENTS.md). `verify` recomputes the fingerprints from the stored ids and
compares them with the independent record committed in `docs/decisions/0002-baseline-window.manifest.json`, so a replaced or
reshuffled window cannot vouch for itself, and it fails closed if that manifest is missing.

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
MANIFEST_PATH = config.REPO_ROOT / "docs" / "decisions" / "0002-baseline-window.manifest.json"


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


def freeze(games: list[dict], path: Path | None = None, n: int = WINDOW_SIZE, manifest_path: Path | None = None) -> dict:
    """Write the window. Created exclusively (O_EXCL) and read-only, so a concurrent or repeated call can never overwrite it.

    If `manifest_path` exists, the new window must match it: a different window is a new version, not a replacement.
    """
    path = path or baseline_path()
    record = build_record(games, n)
    if manifest_path is not None and manifest_path.exists():
        _check_against_manifest(record, json.loads(manifest_path.read_text()))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except FileExistsError as e:
        raise BaselineError(f"{path} already exists: a frozen baseline is never overwritten") from e
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(record, indent=1) + "\n")
    except BaseException:
        path.unlink(missing_ok=True)  # never leave a half-written frozen file behind
        raise
    return record


def _check_against_manifest(record: dict, manifest: dict) -> None:
    """Compare freshly recomputed fingerprints (from the ids) with the independently recorded ones."""
    problems = []
    if record["n"] != manifest["n"]:
        problems.append(f"window size {record['n']} differs from the recorded {manifest['n']}")
    if ids_hash(record["ids"]) != manifest["sha256"]:
        problems.append("the window differs from the independently recorded one (overall fingerprint)")
    if set(record["by_time_control"]) != set(manifest["by_time_control"]):
        problems.append("the time-control lists differ from the recorded ones")
    for label, expected in manifest["by_time_control"].items():
        part = record["by_time_control"].get(label)
        if part is None:
            continue
        if ids_hash(part["ids"]) != expected["sha256"] or len(part["ids"]) != expected["count"]:
            problems.append(f"the {label} list differs from the independently recorded one")
    if problems:
        raise BaselineError("; ".join(problems))


def verify(path: Path | None = None, manifest_path: Path | None = None) -> dict:
    """Check the frozen file against the independently recorded manifest. Raises on any difference.

    The fingerprints stored inside the file are not trusted: they are recomputed from the ids, and the result is compared
    with the committed manifest. A missing manifest is an error (fail closed).
    """
    path = path or baseline_path()
    manifest_path = manifest_path or MANIFEST_PATH
    if not manifest_path.exists():
        raise BaselineError(f"no independent record to verify against: {manifest_path} is missing")
    record = json.loads(path.read_text())
    problems = []
    if ids_hash(record["ids"]) != record["sha256"]:
        problems.append("the stored overall fingerprint does not match the stored ids")
    for label, part in record["by_time_control"].items():
        if ids_hash(part["ids"]) != part["sha256"] or part["count"] != len(part["ids"]):
            problems.append(f"the stored {label} fingerprint or count does not match its ids")
    union = sorted(i for part in record["by_time_control"].values() for i in part["ids"])
    if union != sorted(record["ids"]):
        problems.append("the per-time-control lists do not add up to the window")
    try:
        _check_against_manifest(record, json.loads(manifest_path.read_text()))
    except BaselineError as e:
        problems.append(str(e))
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
        record = freeze(_games(), manifest_path=MANIFEST_PATH) if argv[0] == "freeze" else verify()
    except BaselineError as e:
        sys.exit(str(e))
    print(json.dumps({k: record[k] for k in ("status", "frozen_at", "rule", "n", "sha256")}, indent=1))
    if argv[0] == "verify":
        print("  matches the independent record in docs/decisions/0002-baseline-window.manifest.json")
    for label, part in record["by_time_control"].items():
        print(f"  {label}: {part['count']} games, sha256 {part['sha256']}")


if __name__ == "__main__":
    main(sys.argv[1:])
