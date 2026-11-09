"""Slip cause (ADR 0021): which rule-based detector, if any, confirms why a first slip lost.

  uv run python -m app.learner.slipcause label      # label every first-slip drill (needs Stockfish; reads the evidence cache)
  uv run python -m app.learner.slipcause summary    # drills per cause

A cause comes only from a detector (AGENTS rules 2 and 5): `hanging_own` (the move left a piece to be won), `threat` (it ignored the
opponent's threat), `missed_free` (it passed up a free capture), else `other`, which gives no reason. Labels live in their own file keyed
by drill id, so the drill file is never rewritten. A label from an older detector version is not served. No language model.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

import chess

from app.detectors import hanging_own_v4, missed_free_v3, missed_threat
from app.learner import drillbank, slipwhy

# (cause, detector version, detect function, the outcome that confirms it), in priority order: the first confirming one wins
DETECTORS = (
    ("hanging_own", hanging_own_v4.VERSION, hanging_own_v4.detect, "mistake"),
    ("threat", missed_threat.VERSION, missed_threat.detect, "missed"),
    ("missed_free", missed_free_v3.VERSION, missed_free_v3.detect, "missed"),
)


def set_version(detectors=DETECTORS) -> str:
    """The detector set a label was made under, e.g. `hanging_own@4+threat@4+missed_free@3`. An `other` label means "none of these
    confirmed it", so it is only valid for the set that was run."""
    return "+".join(f"{cause}@{version}" for cause, version, *_ in detectors)


SET_VERSION = set_version()

WORDS = {
    "hanging_own": ("Your move left a piece that the opponent could win.", "Before each move, ask: what can they take after this?"),
    "threat": ("The opponent had a threat, and your move did not deal with it.", "Before each move, ask: what did their last move attack?"),
    "missed_free": ("A free capture was available and you did not take it.", "Before each move, look at every capture, for both sides."),
}


def causes_path():
    return drillbank.bank_dir() / "slip_causes_v1.json"


def label(drill: dict, analyser, detectors=DETECTORS) -> dict:
    """The cause of one drill: the first detector in priority order that confirms the slip, else `other`."""
    board = chess.Board(drill["fen"])
    move = chess.Move.from_uci(drill["played"])
    for cause, version, detect, confirms in detectors:
        finding = detect(board, move, drill["ply"], analyser)
        if finding.outcome == confirms:
            alternatives = [a["uci"] for a in getattr(finding, "alternatives", ())]
            why = slipwhy.build(cause, drill, finding.evidence or {}, alternatives)
            return {"cause": cause, "detector": cause, "version": version, "why": why}
    return {"cause": "other", "detector": None, "version": set_version(detectors)}


def save(labels: dict[str, dict]) -> None:
    path = causes_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, path)  # a reader sees the old file or the new one, never half of one


def _current(entry: dict) -> bool:
    if entry["cause"] == "other":
        return entry["version"] == SET_VERSION
    # a label made before the why existed has no "why" key and is relabelled (the analyses are cached, so it is cheap)
    return "why" in entry and any(c == entry["cause"] and v == entry["version"] for c, v, *_ in DETECTORS)


def load() -> dict[str, dict]:
    """Labels from the current detector versions only; a missing file is no labels."""
    p = causes_path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text())
    except (OSError, ValueError):
        return {}  # unreadable labels read as "no labels": the answer still goes through, with no cause given
    return {k: v for k, v in raw.items() if _current(v)} if isinstance(raw, dict) else {}


def explain_cause(cause: str | None, why: dict | None = None) -> dict:
    """The plain sentence, the habit and the why (sentences with marks) for a cause; anything unknown reads as `other`."""
    if cause in WORDS:
        sentence, habit = WORDS[cause]
        return {"cause": cause, "sentence": sentence, "habit": habit, "why": why}
    return {"cause": "other", "sentence": "No rule-based check confirmed a cause for this one, so there is no reason to give.", "habit": None,
            "why": None}


def label_all() -> dict[str, dict]:
    from app.db.schema import connect
    from app.engine.evidence import open_evidence
    from app.learner import slipbank, slipround

    labels = load()
    todo = [d for d in slipround.read_slips() if d["id"] not in labels]
    with open_evidence(connect(str(slipbank.cache_path()))) as engine:
        for n, d in enumerate(todo, 1):
            labels[d["id"]] = label(d, engine)
            if n % 25 == 0:
                save(labels)  # resumable
                print(n, "of", len(todo), flush=True)
    save(labels)
    return labels


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["label"]:
        label_all()
    elif argv[:1] != ["summary"]:
        print("usage: slipcause label | summary", file=sys.stderr)
        return 2
    print(dict(Counter(v["cause"] for v in load().values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
