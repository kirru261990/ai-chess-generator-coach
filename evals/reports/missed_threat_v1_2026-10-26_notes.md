**Result in one line:** precision 72/72 (1.00), recall 72/100 (0.72). Precision meets the 0.90 target; **recall misses the 0.85 target.**
The detector was not changed and the set was not edited after this run (frozen first, scored once).

**Why recall is low: two problems in the set, found after scoring (so this reading is after the fact).**
1. **The "decided" gate (41 of the 65 disagreements; 25 missed items, 16 met items).** The set kept positions whose best score at
   depth 14 was within 600 cp. The detector skips a position beyond 600 cp at depth 18. These items sit at the edge: the 41 skipped
   items had a median depth-14 score of 532 cp, and 32 of 41 were already at 450 or more. A deeper search pushed them over. This is
   a margin I did not leave in the set (my label rule used the detector's own cut-off at a different depth), not evidence of a
   weak detector. Among the 75 `missed` items the detector did not skip as decided, it called 72 `missed` (0.96); that figure is
   a post-hoc cut and is not the headline.
2. **Engine-only threats (22 of the 65; all `met_real`, label `met`, detector `no_concrete_threat`).** For `met_real` the set accepted
   "passing costs 200 cp" as a threat even without a capture or mate. The detector (ADR 0011) needs a concrete line that mates or
   nets 2 pawns within four plies, so it says no threat. The spec and the set disagree about what counts as a threat; the spec
   was fixed first, so these items are labelled wrongly for M3 and the 3 of 40 `met_real` agreement is a set problem.

**What the numbers do show.** No false `missed` among the 103 items not labelled missed (precision interval 0.95 to 1.00),
including 56 negatives that look like M3 (hung pieces, quiet blunders) and 13 adversarial items (13 of 13 right). Real positions
alone: recall 51/60 = 0.85, with the same two causes. Two `missed` items were called `met:defended_other_loss` and one
`uncertain:threat_line_diverged`; they need a look before anyone concludes the detector is wrong (the item rows below list them).

**Not shown.** Only 1 item is labelled `uncertain`, so the set says nothing about whether `threat_unavoidable` or
`loss_not_stable` are right. No person has reviewed the labels. Puzzle positions are far denser in tactics than real games.

**What to do next (owner's call).** Do not retune the detector on this set. Build `missed_threat_v2`: keep decided items out with a
margin (best score within 400 cp at depth 14, and re-check at depth 18), and accept a `met` label only with a concrete threat
(static, or an engine line that mates or nets 2 pawns within four plies). Then score again and report it as a new set. The hand-check
page on real games (M3d) is the better test of whether real flags are real.
