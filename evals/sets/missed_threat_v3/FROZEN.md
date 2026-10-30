# missed_threat_v3 is FROZEN (2026-10-30)

From this point `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited. Any change means a new version
(`missed_threat_v4`). The builders refuse to overwrite this set, and a test fails if a frozen file changes.

| File | sha256 |
|---|---|
| `positions.jsonl` | `4379cbf96ebf8c49d8fa5da1afb0c3f4a079ca73ee56487dffba85a5f217ced9` |
| `LABEL_RULE.md` | `ce0b2be0f344698cc20d2b9b045da825e985994aad36ceb63827296bf16f8785` |
| `provenance.json` | `d37554def0fd8cd45b54dd68c69c27b08a70f55e45c5c02c37b5d04f8dfc8428` |

## What was frozen
- 84 items from real Lichess Rapid games (both players 600 to 1200): {'not_applicable': 30, 'missed': 29, 'met': 25}. Labels by the independent builder (Stockfish 19
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
