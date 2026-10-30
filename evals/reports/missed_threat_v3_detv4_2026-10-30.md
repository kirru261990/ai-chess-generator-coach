# missed_threat_v3: M3 detector scores (2026-10-30)

Set: frozen `missed_threat_v3` (positions.jsonl sha256 `4379cbf96ebf8c49...`). Detector: `missed_threat` v4 with Stockfish 19 at depth 18 (labels used depth 14 separately). Targets fixed before the run: precision >= 0.9, recall >= 0.85. Positive class = `missed`. Every figure is `successes/denominator` with a 95% Wilson interval. Nothing was tuned on this set.

**All items: precision 26/26 = 1.00 (95% CI 0.87-1.00) (meets the target as a point estimate); recall 26/29 = 0.90 (95% CI 0.74-0.96) (meets the target as a point estimate).**

## Precision and recall for `missed`

| Group | Precision (TP / predicted missed) | Recall (TP / labelled missed) | Exact agreement |
|---|---|---|---|
| all items | 26/26 = 1.00 (95% CI 0.87-1.00) | 26/29 = 0.90 (95% CI 0.74-0.96) | 78/84 = 0.93 (95% CI 0.85-0.97) |
| real positions (real play: missed_real, met_real, hung_not_threat, quiet_blunder) | 26/26 = 1.00 (95% CI 0.87-1.00) | 26/29 = 0.90 (95% CI 0.74-0.96) | 78/84 = 0.93 (95% CI 0.85-0.97) |

## Exact agreement by item category

| Category | Agreement |
|---|---|
| met_clean | 13/15 = 0.87 (95% CI 0.62-0.96) |
| met_other_loss | 9/10 = 0.90 (95% CI 0.60-0.98) |
| missed | 26/29 = 0.90 (95% CI 0.74-0.96) |
| not_applicable | 30/30 = 1.00 (95% CI 0.89-1.00) |

## Confusion matrix, all items (label -> predicted: count)

met->met: 22, met->not_applicable: 3, missed->met: 1, missed->missed: 26, missed->not_applicable: 2, not_applicable->not_applicable: 30

Predicted `uncertain` (the spec's E3 asks for this): 0/84 = 0.00 (95% CI 0.00-0.04).

## Disagreements by detector reason

- met->no_threat:no_concrete_threat: 3
- missed->skipped:already_lost: 2
- missed->met:defended_other_loss: 1

## Every disagreement (6)

| Item | Category | Label | Predicted | Detector outcome:reason | Move | Kind | Loss cp |
|---|---|---|---|---|---|---|---|
| mt3-002 | missed | missed | not_applicable | skipped:already_lost | a4 |  |  |
| mt3-031 | met_other_loss | met | not_applicable | no_threat:no_concrete_threat | Bb5+ |  |  |
| mt3-042 | met_clean | met | not_applicable | no_threat:no_concrete_threat | Rxh5 |  |  |
| mt3-044 | missed | missed | met | met:defended_other_loss | Qf5+ | capture | 1007 |
| mt3-059 | met_clean | met | not_applicable | no_threat:no_concrete_threat | Nxe5 |  |  |
| mt3-095 | missed | missed | not_applicable | skipped:already_lost | d5 |  |  |

## Reading these numbers

# missed_threat_v3, first score of `missed_threat` v2: notes (read before quoting any number)

**Result:** precision 27/28 (0.96, 95% CI 0.82 to 0.99), recall 27/29 (0.93, CI 0.78 to 0.98), exact agreement 77/84. Both targets (0.90 and
0.85) are met **as point estimates only**: the lower ends of the intervals are 0.82 and 0.78. Nothing was tuned on this set; it was frozen
before the detector ran (FROZEN.md), and v2's rule was written before the set was built (ADR 0013).

## What this does not show
- **Not a rate of ignored threats.** Items were chosen by quota, so these figures say how well the detector separates the cases, not how often a
  player misses a threat.
- **The labels are not fully independent of the rule.** The forced-threat test (ADR 0013) and the builder's `missed` rule are the same idea,
  at different depths (14 and 18) and with different code. A match shows v2 is implemented as designed. The idea itself is supported by the
  owner's checks (23 of 24 in round 3) but only on 24 of the 84 items, and the owner could not check the `uncertain` class (kept apart).
- **Static threats only** (a capture or mate the exchange count finds). Quiet threats, forks that the count misses and pins are not covered.
- The set holds no `uncertain` items, so `threat_unavoidable`, `loss_not_stable` and `loss_not_from_threat` are not scored here
  (the private regression run in ADR 0013 saw `loss_not_from_threat` on 6 of 6 defect cases and is regression only).
- Real games at 600 to 1200 on Lichess (start of one month), not the owner's Chess.com games.

## The seven disagreements (each is a lead, not a verdict)
- **Three `met` items the detector calls `no_threat`** (mt3-031, 042, 059): at depth 18 the pass search finds no concrete threat, so the
  detector abstains where the depth-14 builder saw one. Harmless for precision, but they are in the denominator of exact agreement.
- **One false positive: mt3-049 (`met` -> `missed`).** The owner judged this one `met` in round 2 (A yes, B no) and the builder labelled it
  `met` (other loss); the detector says all checks hold. It deserves a look before the M3 hand-check: the same pin or tactic that the
  builder's exchange count cannot see may be at work.
- **Two misses: mt3-044 and mt3-095 (`missed` -> `met`, `defended_other_loss`).** The detector decides the move stops the threat; the
  builder and (for 044) the owner say it did not. 044 is also a case where the loss is large (1007 cp), so another mistake may overlap.
- **One `uncertain`: mt3-048** (`threat_line_diverged`, expected).

## Next
M3 may not be shown as a weakness yet (ADR 0011 (d)): this score passes its first condition. The second is a new owner hand-check on real games
with the new wording (LABEL_RULE Amendment/ADR 0013), gate 27 of 30. Then the real-game rates (TASKS M3e).

