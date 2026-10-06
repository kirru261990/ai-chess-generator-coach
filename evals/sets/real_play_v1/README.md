# real_play_v1 (FROZEN on 2026-10-06; see FROZEN.md)

202 labelled `(position, move)` items for `hanging_own` and `missed_free`, built from real Lichess
puzzle positions plus 22 hand-built adversarial positions, following `LABEL_RULE.md` (v0.2).

| File | What it is |
|---|---|
| `LABEL_RULE.md` | The written rule (v0.4) and the decisions behind it. Read this first. |
| `positions.jsonl` | The items and their labels (ids carry no information about the label). `label` is the outcome with engine evidence; `material_label` is what the board alone shows and what the hand-check validates |
| `provenance.json` | Seed, engine and depth, thresholds, puzzle-file hash, counts, shortfalls |
| `handcheck_owner.html` | **The owner's page: open it in a browser.** Same 30 items as `handcheck_owner.md`, boards with arrows, plain-English questions, buttons, answers saved in the browser, a Copy button. Labels hidden |
| `handcheck_owner.md` | The same 30 items as a text sheet (kept for reference) |
| `handcheck_second.md` | A different 30 plus all adversarial items, for a second reviewer, labels hidden |

Rebuild: `cd backend && uv run python ../evals/tools/build_real_play_set.py` (needs the puzzle file in
`data/lichess/`; deterministic for a given seed and file).

## Composition

| Detector | Stratum | Items |
|---|---|---|
| `missed_free` | `real_taken`: a real puzzle solution that takes a free piece | 40 |
| `missed_free` | `constructed_miss`: another legal move the engine says loses at least 300 cp (marked constructed) | 40 |
| `missed_free` | `no_opportunity`: real positions with a defended capture but no capture that wins material (independent exchange search) | 20 |
| `hanging_own` | `real_blunder`: a real human move that gave up a piece, with a safe alternative available; labelled `missed` if the engine confirms a loss of 300 cp or more, `uncertain` if it does not (under 100 cp). Engine numbers stored per item | 40 |
| `hanging_own` | `real_safe`: a verified solution move, where some other move would have hung a piece | 40 |
| both | `adversarial`: pins, losing captures, several capturers, check, mate versus a free piece, scope | 22 |

Real items: 10 per rating band (400-599, 600-799, 800-999, 1000-1199) per stratum, each from a
different puzzle. 70% of real items carry a mate theme; each item is tagged `mate_theme`, and results are
reported with and without them.

## Human review so far

| Reviewer | Date | Items | Result |
|---|---|---|---|
| Owner (simple page; engine **not** used, confirmed by the owner) | 2026-10-06 | 30 of 202 | 25 agree, 5 disagree (all constructed misses). Independent check supports the label in 5 of 5. Raw result **does not meet** the pass rule as written (see `LABEL_RULE.md` section 9). Answers: `handchecks/owner_answers.txt`; output: `handchecks/owner_result.txt` |
| Second reviewer, GPT (full sheet; `handchecks/second_reviewer_prompt.md`) | 2026-10-06 | 52 | 51 agree, 0 disagree, 1 undecided. python-chess on all 52; Stockfish 19 depth 18 on 29 (22 of 22 and 29 of 29 agree). Notes and answers in `handchecks/` |

## Status

**Frozen on 2026-10-06.** `positions.jsonl`, `LABEL_RULE.md` and `provenance.json` are never edited again (their hashes are in
`FROZEN.md`, and a test enforces it). Any change means a new version, `real_play_v2`. The freeze went ahead although the owner's
raw check did not meet the pass rule as written; `LABEL_RULE.md` section 9 gives the reasons. No detector had been run on the set
at the freeze. Next: run both detectors on it and publish the numbers in `evals/reports/` with each detector's version, every
denominator, and 95% intervals, split by real and constructed items and with and without mate themes.

## Known weaknesses

Puzzle positions are curated tactics, so these items show detection accuracy, not how often mistakes
happen. Constructed items are not real behaviour. Labels are not yet human-reviewed. See
`LABEL_RULE.md` section 11.
