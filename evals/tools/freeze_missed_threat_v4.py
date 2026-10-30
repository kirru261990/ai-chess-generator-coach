"""Freeze `missed_threat_v4` after the owner's check (LABEL_RULE.md). Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/freeze_missed_threat_v4.py

Writes positions.jsonl (every candidate minus the items the owner's check removed), the final provenance.json and FROZEN.md with the
sha256 of each frozen file. Refuses to run twice.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "evals" / "sets" / "missed_threat_v4"
REMOVED = {  # the owner's mapped label differed and it was not a threat the owner missed (LABEL_RULE.md, point 4)
    "mt3-078": {"engine": "met", "owner": "missed",
                "why": "owner: Qxh7 still wins after f5 (a mating attack); the builder's exchange count only sees a pawn"},
    "mt3-069": {"engine": "not_applicable", "owner": "not_applicable",
                "why": "the same position and move as an item of missed_threat_v3 (two games reached it): no position is shared between sets"},
}
OWNER_MISSES_KEPT = {"mt3-082": "owner saw no threat; the exchange count finds Rxf3 with no recapture"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if (SET / "FROZEN.md").exists():
        sys.exit("missed_threat_v4 is already frozen.")
    cands = [json.loads(x) for x in (SET / "candidates.jsonl").read_text().splitlines()]
    frozen, removed = [], []
    for r in cands:
        if r["id"] in REMOVED:
            removed.append({"id": r["id"], "fen": r["fen"], "move_uci": r["move_uci"], **REMOVED[r["id"]]})
        else:
            frozen.append({**r, "category": r["label"] + ("_" + r["met_kind"] if r["label"] == "met" else "")})
    (SET / "positions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in frozen))
    counts = {}
    for r in frozen:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    prov = json.loads((SET / "provenance.json").read_text())
    prov.update({"frozen": True, "frozen_items": len(frozen), "frozen_counts": counts, "removed_by_owner_check": removed,
                 "owner_misses_kept": OWNER_MISSES_KEPT, "owner_check": "22 of 24 agree (gate 20); missed 7/8, met 7/8, not_applicable 8/8",
                 "detectors_run": False})
    (SET / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    names = ("positions.jsonl", "LABEL_RULE.md", "provenance.json")
    rows = "\n".join(f"| `{n}` | `{sha(SET / n)}` |" for n in names)
    (SET / "FROZEN.md").write_text(f"""# missed_threat_v4 is FROZEN (2026-10-31)

From this point `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited. Any change means a new version
(`missed_threat_v5`). The builders refuse to overwrite this set, and a test fails if a frozen file changes.

| File | sha256 |
|---|---|
{rows}

## What was frozen
- {len(frozen)} items from real Lichess Rapid games (both players 600 to 1200), games not used by `missed_threat_v3`: {counts}. Labels by the independent
  builder (Stockfish 19 depth 14, exchange count), checked by the owner on 24 items (blue-arrow page): **22 of 24 agree, gate 20 met first time**.
- One item the owner's check contradicted was removed (mt3-078: the builder's exchange count missed a mating attack), and one that duplicates a `missed_threat_v3` position (mt3-069). One item where the
  owner saw no threat but the exchange count finds one was kept (mt3-082). The owner had help from the assistant on one board (question 3, a
  check that forces the reply; the answer matches the label).
- No detector has been run on it (`detectors_run: false`).

## To be scored against it
`missed_threat` v3 (ADR 0014) with the evidence engine (depth 18), `evals/tools/score_missed_threat.py --set missed_threat_v4`. Targets fixed before
the run: precision >= 0.90, recall >= 0.85. Report v2's score on `missed_threat_v3` next to it and the limits (static threats only, the
exchange count does not see pins or mating attacks, 24 items checked by a person).
""")
    print(len(frozen), counts, "removed:", [r["id"] for r in removed])


if __name__ == "__main__":
    main()
