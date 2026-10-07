"""Self-reported intents, stored as the player wrote them (spec D2). Under data/ (git-ignored), one JSON line each."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app import config


def path() -> Path:
    return config.DATA_DIR / "intents" / "intents_v1.jsonl"


def save(game_id: str, ply: int, answer: str, comparison: dict, facts: list[dict]) -> None:
    record = {
        "game_id": game_id,
        "ply": ply,
        "answer": answer,
        "self_reported": True,  # what the player said, never inferred
        "facts": [f["id"] for f in facts],
        "comparison": {k: comparison[k] for k in ("status", "mentioned", "model", "prompt")},
        "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(record) + "\n")
