# missed_threat_v1 is FROZEN (2026-10-26)

From this point `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited. Any change means a new version
(`missed_threat_v2`). The builder refuses to overwrite this set, and a test fails if any of the three files changes.

| File | sha256 |
|---|---|
| `positions.jsonl` | `7db34557b08a2c2b5bbf97c222c945606cef0d94dc19a21b6e320d0a2604b9ef` |
| `LABEL_RULE.md` | `7850968e25c89cb6169216c7cec1987e0b4071c240df3b56b5044dfd1913f780` |
| `provenance.json` | `d17c0d0219adce7469cb94aeae93316909d2e10f707f392fddec1d25c6f92bdc` |

Recorded for reproduction (not enforced): builder `evals/tools/build_missed_threat_set.py` sha256 `a707e7710658f5cf8016620ebd8de22917635e85e939787274f814508359dc03`;
seed 20261026; Stockfish 19 at depth 14; base commit `6c3cd90` (the freeze commit follows it).

## What was frozen
- 203 items: 100 missed, 43 met, 59 not_applicable, 1 uncertain; 13 hand-built or opening-line adversarial items, the rest from Lichess puzzles.
- No detector had been run on this set at the freeze (`provenance.json`: `detectors_run: false`). No person has reviewed the labels.

## To be scored against it
`missed_threat` v1 with the evidence engine (depth 18). Targets fixed before the run: precision >= 0.90, recall >= 0.85 for `missed`.
