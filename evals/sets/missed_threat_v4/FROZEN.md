# missed_threat_v4 is FROZEN (2026-10-31)

From this point `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited. Any change means a new version
(`missed_threat_v5`). The builders refuse to overwrite this set, and a test fails if a frozen file changes.

| File | sha256 |
|---|---|
| `positions.jsonl` | `d96bdf74cc563c6dde9f5afaf6c530e561709158da17f45ccc0ff3726124d9ad` |
| `LABEL_RULE.md` | `d2b7940c056dc40d51520d781f541ca86243cf0830fe61bddf67bcdc6bc13941` |
| `provenance.json` | `195582590f0dcf73baf82f4facf637b697286943b4616daa1b3dda73afd2032b` |

## What was frozen
- 88 items from real Lichess Rapid games (both players 600 to 1200), games not used by `missed_threat_v3`: {'not_applicable': 29, 'missed': 30, 'met': 29}. Labels by the independent
  builder (Stockfish 19 depth 14, exchange count), checked by the owner on 24 items (blue-arrow page): **22 of 24 agree, gate 20 met first time**.
- One item the owner's check contradicted was removed (mt3-078: the builder's exchange count missed a mating attack), and one that duplicates a `missed_threat_v3` position (mt3-069). One item where the
  owner saw no threat but the exchange count finds one was kept (mt3-082). The owner had help from the assistant on one board (question 3, a
  check that forces the reply; the answer matches the label).
- No detector has been run on it (`detectors_run: false`).

## To be scored against it
`missed_threat` v3 (ADR 0014) with the evidence engine (depth 18), `evals/tools/score_missed_threat.py --set missed_threat_v4`. Targets fixed before
the run: precision >= 0.90, recall >= 0.85. Report v2's score on `missed_threat_v3` next to it and the limits (static threats only, the
exchange count does not see pins or mating attacks, 24 items checked by a person).
