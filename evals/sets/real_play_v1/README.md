# real_play_v1 (DRAFT, not frozen; no detector has been run on it)

202 labelled `(position, move)` items for `hanging_own` and `missed_free`, built from real Lichess
puzzle positions plus 22 hand-built adversarial positions, following `LABEL_RULE.md` (v0.2).

| File | What it is |
|---|---|
| `LABEL_RULE.md` | The written rule (v0.3) and the decisions behind it. Read this first. |
| `positions.jsonl` | The items and their labels (ids carry no information about the label) |
| `provenance.json` | Seed, engine and depth, thresholds, puzzle-file hash, counts, shortfalls |
| `handcheck_owner.md` | 30 items for the owner, labels hidden |
| `handcheck_second.md` | A different 30 plus all adversarial items, for a second reviewer, labels hidden |

Rebuild: `cd backend && uv run python ../evals/tools/build_real_play_set.py` (needs the puzzle file in
`data/lichess/`; deterministic for a given seed and file).

## Composition

| Detector | Stratum | Items |
|---|---|---|
| `missed_free` | `real_taken`: a real puzzle solution that takes a free piece | 40 |
| `missed_free` | `constructed_miss`: another legal move the engine says loses at least 300 cp (marked constructed) | 40 |
| `missed_free` | `no_opportunity`: real positions with a defended capture but no capture that wins material (independent exchange search) | 20 |
| `hanging_own` | `real_blunder`: a real human move that gave up a piece | 40 |
| `hanging_own` | `real_safe`: a verified solution move | 40 |
| both | `adversarial`: pins, losing captures, several capturers, check, mate versus a free piece, scope | 22 |

Real items: 10 per rating band (400-599, 600-799, 800-999, 1000-1199) per stratum, each from a
different puzzle. 70% of real items carry a mate theme; each item is tagged `mate_theme`, and results are
reported with and without them.

## Status and what must happen next (LABEL_RULE.md section 8)

1. **Hand-check** (section 9 of the rule, which also maps the answers A, B, C to labels): owner and a second reviewer answer the yes/no questions, labels hidden.
   Pass rule: at most 3 of 30 disagreements. If it fails, the rule is revised and this becomes v2.
2. **Freeze:** record the sha256 of `LABEL_RULE.md` and `positions.jsonl` in `HANDOFF.md`.
3. **Only then** run the detectors and publish the numbers in `evals/reports/` with each
   detector's version and every denominator.

## Known weaknesses

Puzzle positions are curated tactics, so these items show detection accuracy, not how often mistakes
happen. Constructed items are not real behaviour. Labels are not yet human-reviewed. See
`LABEL_RULE.md` section 11.
