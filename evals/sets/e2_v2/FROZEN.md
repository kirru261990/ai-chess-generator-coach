# e2_v2 is FROZEN (2026-10-08)

From this point the set, the three prompts below and the coach prompt `why_v2` are never edited. Any change means a new version
and a new run. A test fails if one of these files changes. Why this set exists and what changed since v1:
`docs/decisions/0004-e2-v2-changes.md`. Design and limits: `docs/decisions/0003-e2-eval-design.md`.

| File | sha256 |
|---|---|
| `evals/sets/e2_v2/positions.jsonl` | `ea9f8b0831ab7931994be0d828bb8902038a45b06c00f2640236ed514ff98c5a` |
| `evals/sets/e2_v2/provenance.json` | `a5f5b0ed4088cb11810cc2e8ef6356ed0fca650214dd88ca7bdbb32cbcbb842e` |
| `evals/tools/prompts/extract_v2.md` | `f840857b0bbd499cac11c83eb4ae95c75d9f3924cba852bb83a92e3c1b1e0836` |
| `evals/tools/prompts/raw_v1.md` | `8f897dca466cc4a46d02059189e4e5019bcaf49e35e1bbcbb9e8a38ce5081196` |
| `backend/app/coach/prompts/why_v2.md` | `99808d64bf5de2aa4d2bab215af28b19010b2aed010b5809cbaabec4c4c85957` |

Recorded for reproduction (not enforced): `evals/tools/run_e2.py` sha256 `ad63e2cf4e872a2b8dd82d0efc20c5a1542341091900442f19d77fc99981533e`; builder
`evals/tools/build_e2_set.py` sha256 `11069993c73ad07391bee94eff4530f155ede023298774be7cae87536926e664`; verifier `backend/app/coach/verifier.py` sha256
`de50b1613fc39b7cd824e2656c7e99c985391609b12150d0671373d7eba58a94` (version 2); seed 20261009; Stockfish 19 (built at depth 14, scored at depth 18);
detectors `hanging_own` v2 and `missed_free` v2; coach model `claude-sonnet-5-5`.

## What was frozen
- 50 new items from the Lichess puzzle database (CC0): 25 good moves and 25 engine-confirmed mistakes; none of the e2_v1 or
  pilot puzzles. No human has reviewed them.
- The instruments were tuned on e2_v1 positions (a development run, see the ADR). No result on this set had been seen at the freeze.

## What may still change
Documentation next to the set and anything under `evals/reports/`. The frozen files may not.
