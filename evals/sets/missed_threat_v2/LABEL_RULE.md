# missed_threat_v2: label rule (written before any detector ran on this set)

v2 follows `missed_threat_v1/LABEL_RULE.md` (purpose, independence, definitions, categories, scoring) except for the changes
below. They answer the v1 score (`evals/reports/missed_threat_v1_2026-10-26_notes.md`), which showed two flaws in v1 itself.
The detector (`missed_threat` v1) has not changed.

## Changes from v1
1. **Calm positions only.** v1 kept positions within 600 cp at depth 14, the detector's own cut-off at a different depth, so many
   were skipped as "decided". v2 needs the best move within **400 cp at depth 14 and within 550 cp at depth 18** (the detector's
   depth). Applies to every real and constructed category and to hand-built items.
2. **`met` needs a concrete threat.** A `met_real` item needs a static threat (as in v1) **or** an engine line, for the opponent
   after the pass at depth 14, that mates or nets at least 2 pawns within 4 plies by the builder's own material count
   (`threat_basis`: `static` or `engine_line`). A pass cost of 200 cp alone is no longer enough; it is also still required.
3. **Fresh puzzles.** No puzzle used in v1 is used again (a test checks it). New seed `20261027`.
4. Two hand-built positions were made calmer (the fork position lost a pawn; the trapped knight lost a pawn), one move was changed
   to match (g6 instead of h6). Their reasons are unchanged.

## What did not work (stated before scoring)
- **`uncertain` ("nothing can stop the threat") items.** I tried to add about 24 from puzzles (a static threat that the engine's
  best move does not stop, passing costing under 150 cp, calm position): not one passed in 6,000 positions, because the solver
  is usually already winning or the pass cost is large. I also tried random positions with a trapped knight; their labels did not
  hold up (engine scores near zero), so I dropped them rather than ship labels I do not trust. **v2 has one `uncertain` item
  (hand-built), as v1 did, so the set cannot judge `threat_unavoidable` or `loss_not_stable`.**
- **Fewer `met_real` items.** With the calm and concrete-threat rules, the 400 and 600 rating bands ran short (24 items instead
  of 40). `constructed_missed` is also short in those bands (22 instead of 40). Shortfalls are in `provenance.json`.

## Scoring (same as v1, fixed before the run)
Positive class `missed`; precision and recall with 95% Wilson intervals for all items and the real (not constructed) and constructed
groups, targets precision >= 0.90 and recall >= 0.85, plus the uncertain rate and every disagreement. Nothing is tuned on this set.
Reported next to v1, not instead of it: v1 stays the record of the first score.
