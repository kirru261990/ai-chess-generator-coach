# missed_threat_v1: M3 detector scores (2026-10-26)

Set: frozen `missed_threat_v1` (positions.jsonl sha256 `7db34557b08a2c2b...`). Detector: `missed_threat` v1 with Stockfish 19 at depth 18 (labels used depth 14 separately). Targets fixed before the run: precision >= 0.9, recall >= 0.85. Positive class = `missed`. Every figure is `successes/denominator` with a 95% Wilson interval. Nothing was tuned on this set.

**All items: precision 72/72 = 1.00 (95% CI 0.95-1.00) (meets the target as a point estimate); recall 72/100 = 0.72 (95% CI 0.63-0.80) (misses the target as a point estimate).**

## Precision and recall for `missed`

| Group | Precision (TP / predicted missed) | Recall (TP / labelled missed) | Exact agreement |
|---|---|---|---|
| all items | 72/72 = 1.00 (95% CI 0.95-1.00) | 72/100 = 0.72 (95% CI 0.63-0.80) | 138/203 = 0.68 (95% CI 0.61-0.74) |
| real positions (real_*) | 51/51 = 1.00 (95% CI 0.93-1.00) | 51/60 = 0.85 (95% CI 0.74-0.92) | 110/156 = 0.71 (95% CI 0.63-0.77) |
| constructed (constructed_missed + adversarial) | 21/21 = 1.00 (95% CI 0.85-1.00) | 21/40 = 0.53 (95% CI 0.37-0.67) | 48/67 = 0.72 (95% CI 0.60-0.81) |
| adversarial only | 6/6 = 1.00 (95% CI 0.61-1.00) | 6/6 = 1.00 (95% CI 0.61-1.00) | 13/13 = 1.00 (95% CI 0.77-1.00) |

## Exact agreement by item category

| Category | Agreement |
|---|---|
| adversarial | 13/13 = 1.00 (95% CI 0.77-1.00) |
| constructed_missed | 15/34 = 0.44 (95% CI 0.29-0.61) |
| constructed_quiet | 20/20 = 1.00 (95% CI 0.84-1.00) |
| hung_not_threat | 20/20 = 1.00 (95% CI 0.84-1.00) |
| met_real | 3/40 = 0.07 (95% CI 0.03-0.20) |
| missed_real | 51/60 = 0.85 (95% CI 0.74-0.92) |
| quiet_blunder | 16/16 = 1.00 (95% CI 0.81-1.00) |

## Confusion matrix, all items (label -> predicted: count)

met->met: 6, met->not_applicable: 37, missed->met: 2, missed->missed: 72, missed->not_applicable: 25, missed->uncertain: 1, not_applicable->not_applicable: 59, uncertain->uncertain: 1

Predicted `uncertain` (the spec's E3 asks for this): 2/203 = 0.01 (95% CI 0.00-0.04).

## Disagreements by detector reason

- missed->skipped:decided: 25
- met->no_threat:no_concrete_threat: 22
- met->skipped:decided: 15
- missed->met:defended_other_loss: 2
- missed->uncertain:threat_line_diverged: 1

## Every disagreement (65)

| Item | Category | Label | Predicted | Detector outcome:reason | Move | Kind | Loss cp |
|---|---|---|---|---|---|---|---|
| mt1-002 | met_real | met | not_applicable | skipped:decided | a4 |  |  |
| mt1-006 | met_real | met | not_applicable | no_threat:no_concrete_threat | Rxb5+ |  |  |
| mt1-007 | constructed_missed | missed | not_applicable | skipped:decided | Kh5 |  |  |
| mt1-013 | met_real | met | not_applicable | skipped:decided | Qxc4+ |  |  |
| mt1-019 | constructed_missed | missed | met | met:defended_other_loss | Nd4 | other | 1368 |
| mt1-025 | met_real | met | not_applicable | no_threat:no_concrete_threat | Bxd4+ |  |  |
| mt1-027 | constructed_missed | missed | not_applicable | skipped:decided | h4 |  |  |
| mt1-030 | met_real | met | not_applicable | no_threat:no_concrete_threat | h5 |  |  |
| mt1-034 | met_real | met | not_applicable | no_threat:no_concrete_threat | Kxf5 |  |  |
| mt1-037 | missed_real | missed | not_applicable | skipped:decided | Rd1 |  |  |
| mt1-041 | constructed_missed | missed | not_applicable | skipped:decided | Kf2 |  |  |
| mt1-043 | met_real | met | not_applicable | no_threat:no_concrete_threat | b4 |  |  |
| mt1-044 | met_real | met | not_applicable | no_threat:no_concrete_threat | Rxd7 |  |  |
| mt1-047 | missed_real | missed | not_applicable | skipped:decided | Nxe4 |  |  |
| mt1-060 | met_real | met | not_applicable | no_threat:no_concrete_threat | Kxb4 |  |  |
| mt1-065 | met_real | met | not_applicable | no_threat:no_concrete_threat | gxh4 |  |  |
| mt1-066 | constructed_missed | missed | not_applicable | skipped:decided | Kb8 |  |  |
| mt1-067 | met_real | met | not_applicable | skipped:decided | Rxe2+ |  |  |
| mt1-069 | constructed_missed | missed | not_applicable | skipped:decided | f5 |  |  |
| mt1-073 | constructed_missed | missed | not_applicable | skipped:decided | Kb5 |  |  |
| mt1-074 | met_real | met | not_applicable | skipped:decided | Rf8+ |  |  |
| mt1-075 | missed_real | missed | not_applicable | skipped:decided | Rd2 |  |  |
| mt1-076 | met_real | met | not_applicable | no_threat:no_concrete_threat | Nd7+ |  |  |
| mt1-078 | met_real | met | not_applicable | skipped:decided | Kg5 |  |  |
| mt1-079 | met_real | met | not_applicable | no_threat:no_concrete_threat | gxf4 |  |  |
| mt1-080 | met_real | met | not_applicable | no_threat:no_concrete_threat | Bxb7 |  |  |
| mt1-082 | met_real | met | not_applicable | skipped:decided | fxe4+ |  |  |
| mt1-083 | missed_real | missed | not_applicable | skipped:decided | Nf3 |  |  |
| mt1-087 | missed_real | missed | not_applicable | skipped:decided | gxf4 |  |  |
| mt1-088 | met_real | met | not_applicable | skipped:decided | Qxg4+ |  |  |
| mt1-093 | constructed_missed | missed | not_applicable | skipped:decided | h4 |  |  |
| mt1-095 | met_real | met | not_applicable | no_threat:no_concrete_threat | Kxd6 |  |  |
| mt1-097 | met_real | met | not_applicable | skipped:decided | Nf5+ |  |  |
| mt1-099 | missed_real | missed | not_applicable | skipped:decided | Bxe1 |  |  |
| mt1-100 | constructed_missed | missed | not_applicable | skipped:decided | Kg1 |  |  |
| mt1-104 | met_real | met | not_applicable | no_threat:no_concrete_threat | b5 |  |  |
| mt1-106 | constructed_missed | missed | not_applicable | skipped:decided | Kh3 |  |  |
| mt1-110 | met_real | met | not_applicable | no_threat:no_concrete_threat | b4 |  |  |
| mt1-112 | met_real | met | not_applicable | skipped:decided | Kc4 |  |  |
| mt1-114 | met_real | met | not_applicable | no_threat:no_concrete_threat | bxc5 |  |  |
| mt1-115 | met_real | met | not_applicable | no_threat:no_concrete_threat | a4 |  |  |
| mt1-116 | constructed_missed | missed | not_applicable | skipped:decided | Kh2 |  |  |
| mt1-120 | met_real | met | not_applicable | no_threat:no_concrete_threat | Nxd7 |  |  |
| mt1-122 | constructed_missed | missed | not_applicable | skipped:decided | Kg3 |  |  |
| mt1-124 | met_real | met | not_applicable | no_threat:no_concrete_threat | f2 |  |  |
| mt1-126 | constructed_missed | missed | not_applicable | skipped:decided | g3 |  |  |
| mt1-127 | met_real | met | not_applicable | skipped:decided | a5 |  |  |
| mt1-133 | constructed_missed | missed | not_applicable | skipped:decided | Kh8 |  |  |
| mt1-136 | missed_real | missed | not_applicable | skipped:decided | c2 |  |  |
| mt1-139 | constructed_missed | missed | not_applicable | skipped:decided | g4 |  |  |
| mt1-140 | constructed_missed | missed | not_applicable | skipped:decided | Ka2 |  |  |
| mt1-147 | constructed_missed | missed | uncertain | uncertain:threat_line_diverged | Kd2 | other | 1346 |
| mt1-148 | met_real | met | not_applicable | no_threat:no_concrete_threat | d7 |  |  |
| mt1-150 | met_real | met | not_applicable | skipped:decided | Ke5 |  |  |
| mt1-151 | met_real | met | not_applicable | skipped:decided | Rxf4 |  |  |
| mt1-155 | met_real | met | not_applicable | no_threat:no_concrete_threat | f5 |  |  |
| mt1-161 | constructed_missed | missed | not_applicable | skipped:decided | Kd4 |  |  |
| mt1-162 | met_real | met | not_applicable | skipped:decided | b4 |  |  |
| mt1-165 | met_real | met | not_applicable | no_threat:no_concrete_threat | fxe5 |  |  |
| mt1-172 | met_real | met | not_applicable | skipped:decided | Kxa3 |  |  |
| mt1-176 | met_real | met | not_applicable | no_threat:no_concrete_threat | h4 |  |  |
| mt1-177 | met_real | met | not_applicable | skipped:decided | Be4 |  |  |
| mt1-181 | missed_real | missed | not_applicable | skipped:decided | Nxf5 |  |  |
| mt1-191 | constructed_missed | missed | not_applicable | skipped:decided | Kf6 |  |  |
| mt1-203 | missed_real | missed | met | met:defended_other_loss | Re8 | mate | 1049 |

## Reading these numbers

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

