# e2_v1 is FROZEN (2026-10-07)

From this point the set, the three prompts below and the coach prompt `why_v1` are never edited. Any change means a new version
(`e2_v2`, `why_v2`, ...) and a new run. A test fails if one of these files changes. Design, scoring and limits:
`docs/decisions/0003-e2-eval-design.md`.

| File | sha256 |
|---|---|
| `evals/sets/e2_v1/positions.jsonl` | `461069d5fabb62addf12530dca5d43dcbd1b3e62e40bb730f83e89e71353577f` |
| `evals/sets/e2_v1/provenance.json` | `515734fdc49d0e55d235957e0c7ac1e442993cfb4fc6983e508de7b176208544` |
| `evals/tools/prompts/extract_v1.md` | `a488209f5deada04c8073d1083eb6a8dd5b9ffb2c350b19de2e91f49b6dc25c0` |
| `evals/tools/prompts/raw_v1.md` | `8f897dca466cc4a46d02059189e4e5019bcaf49e35e1bbcbb9e8a38ce5081196` |
| `backend/app/coach/prompts/why_v1.md` | `6b29f208bdcba2a323c0c743e8811cb3bcfeaa3bfa014c178fc5b63eabd90224` |

Recorded for reproduction (not enforced): `evals/tools/run_e2.py` sha256 `9a00b90ba1c3b32da180fbb945e61964c533e8ce1c336add45aaae8debeef7f7`; builder `evals/tools/build_e2_set.py`
sha256 `0baf407eeea4aaf2324f90c0fabfcafe4ec0fff8634a817c09e0f65b29c7908a`; seed 20261008; Stockfish 19 (set built at depth 14, scored at depth 18); verifier version 1;
detectors `hanging_own` v2 and `missed_free` v2; coach model `claude-sonnet-5-5`.

## What was frozen
- 50 items from the Lichess puzzle database (CC0): 25 good moves and 25 engine-confirmed mistakes. Five pilot puzzles were
  excluded. No human has reviewed the items.
- The runner was debugged on 5 throwaway pilot items before the freeze; no result on this set had been seen at the freeze.

## What may still change
`README` text next to the set and anything under `evals/reports/`. The frozen files may not. The runner may be fixed for bugs
only if the fix is recorded in the report and cannot change what is scored.
