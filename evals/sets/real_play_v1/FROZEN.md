# real_play_v1 is FROZEN (2026-10-06)

From this point `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited. Any change, however small,
means a new version (`real_play_v2`). The builder refuses to overwrite this set, and a test fails if any of the three
files below changes.

| File | sha256 |
|---|---|
| `positions.jsonl` | `d3b449686fdd2141b13ae266b90b75eb60a7d490c94030d23b12ead4fa1633bf` |
| `LABEL_RULE.md` | `2f454c577f7e18407e7c99f9ede96021ab56ebfc664edd4fbb3e207a89972ec6` |
| `provenance.json` | `aefade53d9f5118ae2bdda24e68631636a9828c9405517a6dbdec3b2cc3787b3` |

Recorded for reproduction (not enforced): builder `evals/tools/build_real_play_set.py` sha256 `b893363c9b67a7be0170d46109d0f48e1aa683e4f39804dd6d10f307b4ebbf16`;
puzzle file `lichess_db_puzzle.csv.zst` sha256 `76335bfa7d7c4a7f93c1366d81549e53951ebb79dd43d34904cab8f22d962f8d`; seed 20261007; Stockfish 19 at depth 14;
repository commit at the freeze: `dc9590f` (the freeze commit itself follows it).

## What was frozen, and the review behind it
- 202 items: 180 real (Lichess puzzles) and 22 hand-built adversarial; each real item confirmed by an independent exchange search.
- Owner review: 30 items, 25 agree, 5 disagree; the 5 were adjudicated and the label was supported in 5 of 5. **The raw result did not
  meet the pass rule as written** (at most 3 disagreements, no pattern); the freeze went ahead for the reasons in `LABEL_RULE.md` section 9.
- Second reviewer (GPT): 52 items, 51 agree, 0 disagree, 1 undecided; python-chess on all, Stockfish depth 18 on 29.
- 82 of 202 items had some review; no label error was found. No strong human player has reviewed it.
- No detector had been run on this set at the freeze.

## To be scored against it (versions are part of the result)
`hanging_own` v2, `missed_free` v2. Report every number with its detector version, its denominator and a 95% interval, split
by real and constructed items and with and without mate-theme items (`LABEL_RULE.md` section 10).

## What may still change
Documentation next to the set (`README.md`, `handchecks/`) and anything under `evals/reports/`. The frozen files may not.
