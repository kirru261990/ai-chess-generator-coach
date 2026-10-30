"""Freeze `missed_threat_v3` after the owner's two check rounds (LABEL_RULE.md, Amendments 1 and 2). Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/freeze_missed_threat_v3.py

Writes positions.jsonl (every candidate that is not `uncertain`, minus the items the owner's check removed), uncertain_unverified.jsonl
(the `uncertain` candidates: not frozen, not scored with the set), the final provenance.json and FROZEN.md with the sha256 of each frozen
file. Refuses to run twice.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "evals" / "sets" / "missed_threat_v3"
REMOVED = {  # owner's mapped label differed and it was not a threat the owner missed (Amendment 1, point 4): round 2, item mt3-014
    "mt3-014": {"engine": "missed", "owner": "uncertain", "why": "owner: the move also loses something else (D yes)"},
}
OWNER_MISSES_KEPT = {  # the exchange count finds a threat the owner did not see; kept (Amendment 1, point 4)
    "mt3-063": "a mate in one (Qh4#) the owner did not see", "mt3-067": "owner saw no threat on a met_other_loss item",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if (SET / "FROZEN.md").exists():
        sys.exit("missed_threat_v3 is already frozen.")
    cands = [json.loads(x) for x in (SET / "candidates.jsonl").read_text().splitlines()]
    frozen, unverified, removed = [], [], []
    for r in cands:
        if r["id"] in REMOVED:
            removed.append({"id": r["id"], "fen": r["fen"], "move_uci": r["move_uci"], **REMOVED[r["id"]]})
        elif r["label"] == "uncertain":
            unverified.append(r)
        else:
            frozen.append({**r, "category": r["label"] + ("_" + r["met_kind"] if r["label"] == "met" else "")})
    (SET / "positions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in frozen))
    (SET / "uncertain_unverified.jsonl").write_text("".join(json.dumps(r) + "\n" for r in unverified))
    prov = json.loads((SET / "provenance.json").read_text())
    counts = {}
    for r in frozen:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    prov.update({"frozen": True, "frozen_items": len(frozen), "frozen_counts": counts, "uncertain_unverified": len(unverified),
                 "removed_by_owner_check": removed, "owner_misses_kept": OWNER_MISSES_KEPT,
                 "owner_check": {"round1": "10 of 24 (labels had a builder defect, fixed in Amendment 1)",
                                 "round2": "15 of 24; missed, met, not_applicable 15 of 18; uncertain 0 of 6 (cannot be judged by the owner)"},
                 "detectors_run": False, "exception": "frozen without meeting the 20-of-24 gate (Amendment 2); `uncertain` items excluded"})
    (SET / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    names = ("positions.jsonl", "LABEL_RULE.md", "provenance.json")
    rows = "\n".join(f"| `{n}` | `{sha(SET / n)}` |" for n in names)
    (SET / "FROZEN.md").write_text(f"""# missed_threat_v3 is FROZEN (2026-10-30)

From this point `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited. Any change means a new version
(`missed_threat_v4`). The builders refuse to overwrite this set, and a test fails if a frozen file changes.

| File | sha256 |
|---|---|
{rows}

## What was frozen
- {len(frozen)} items from real Lichess Rapid games (both players 600 to 1200): {counts}. Labels by the independent builder (Stockfish 19
  depth 14, exchange count), checked by the owner on a sample of 24 in two rounds.
- **Exception, declared after the results:** the gate was 20 of 24 and was not met (10, then 15). The `uncertain` class (15 candidates) is
  **excluded and kept apart** in `uncertain_unverified.jsonl` (not frozen, not scored with this set) because the owner cannot judge it
  (0 of 6). The other three classes agreed on 15 of 18 (83%). One item the owner's check contradicted was removed (mt3-014).
  Two items where the owner missed a threat the exchange count finds were kept (mt3-063, mt3-067). See `check_round1.md`, `check_round2.md`
  and LABEL_RULE.md Amendment 2.
- No detector has been run on it (`detectors_run: false`).

## To be scored against it
`missed_threat` v2 with the evidence engine (depth 18), by `evals/tools/score_missed_threat.py --set missed_threat_v3`. Targets (fixed
before the run): precision >= 0.90, recall >= 0.85. Report the set's limits next to the numbers: only 24 items were checked by a person,
static threats only, and a 600 to 1200 owner could not verify some labels.
""")
    print(len(frozen), counts, "uncertain apart:", len(unverified), "removed:", [r["id"] for r in removed])


if __name__ == "__main__":
    main()
