# missed_threat_v2 is FROZEN (2026-10-26)

From this point `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited. Any change means a new version
(`missed_threat_v3`). The builder refuses to overwrite this set, and a test fails if any of the three files changes.

| File | sha256 |
|---|---|
| `positions.jsonl` | `a334c27597a6410318d6182cec505cbc618eea013fd503b2ce62fb16da0fb9ee` |
| `LABEL_RULE.md` | `bbaabe8a45a8bd281fcb2b3b3233a0788a4f79e5e3be7660c05264ac288df350` |
| `provenance.json` | `a827e5fd9ff195012779011d45f9665de05e841c2a8195150b2f9a79a634b536` |

Recorded for reproduction (not enforced): builder `evals/tools/build_missed_threat_set_v2.py` sha256 `162edb5d39ad06c738932d23cafc3a37d52d1f3564dd324a47244770cf93eec1`
(it uses the v1 builder as a library); seed 20261027; Stockfish 19 at depth 14; base commit `3730107` (the freeze commit follows it).

## What was frozen
- 175 items: 88 missed, 27 met, 59 not_applicable, 1 uncertain; 13 hand-built or opening-line items, the rest from Lichess puzzles.
- No detector had been run on it (`provenance.json`: `detectors_run: false`). No person has reviewed the labels.

## To be scored against it
`missed_threat` v1 with the evidence engine (depth 18). Targets fixed before the run: precision >= 0.90, recall >= 0.85.
