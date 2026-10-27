# missed_threat_v2: M3 detector scores (2026-10-26)

Set: frozen `missed_threat_v2` (positions.jsonl sha256 `a334c27597a64103...`). Detector: `missed_threat` v1 with Stockfish 19 at depth 18 (labels used depth 14 separately). Targets fixed before the run: precision >= 0.9, recall >= 0.85. Positive class = `missed`. Every figure is `successes/denominator` with a 95% Wilson interval. Nothing was tuned on this set.

**All items: precision 84/85 = 0.99 (95% CI 0.94-1.00) (meets the target as a point estimate); recall 84/88 = 0.95 (95% CI 0.89-0.98) (meets the target as a point estimate).**

## Precision and recall for `missed`

| Group | Precision (TP / predicted missed) | Recall (TP / labelled missed) | Exact agreement |
|---|---|---|---|
| all items | 84/85 = 0.99 (95% CI 0.94-1.00) | 84/88 = 0.95 (95% CI 0.89-0.98) | 166/175 = 0.95 (95% CI 0.91-0.97) |
| real positions (real play: missed_real, met_real, hung_not_threat, quiet_blunder) | 58/58 = 1.00 (95% CI 0.94-1.00) | 58/60 = 0.97 (95% CI 0.89-0.99) | 114/120 = 0.95 (95% CI 0.90-0.98) |
| constructed (constructed_missed, constructed_quiet, adversarial) | 26/27 = 0.96 (95% CI 0.82-0.99) | 26/28 = 0.93 (95% CI 0.77-0.98) | 52/55 = 0.95 (95% CI 0.85-0.98) |
| adversarial only | 6/7 = 0.86 (95% CI 0.49-0.97) | 6/6 = 1.00 (95% CI 0.61-1.00) | 12/13 = 0.92 (95% CI 0.67-0.99) |

## Exact agreement by item category

| Category | Agreement |
|---|---|
| adversarial | 12/13 = 0.92 (95% CI 0.67-0.99) |
| constructed_missed | 20/22 = 0.91 (95% CI 0.72-0.97) |
| constructed_quiet | 20/20 = 1.00 (95% CI 0.84-1.00) |
| hung_not_threat | 20/20 = 1.00 (95% CI 0.84-1.00) |
| met_real | 20/24 = 0.83 (95% CI 0.64-0.93) |
| missed_real | 58/60 = 0.97 (95% CI 0.89-0.99) |
| quiet_blunder | 16/16 = 1.00 (95% CI 0.81-1.00) |

## Confusion matrix, all items (label -> predicted: count)

met->met: 23, met->not_applicable: 4, missed->met: 2, missed->missed: 84, missed->not_applicable: 2, not_applicable->not_applicable: 59, uncertain->missed: 1

Predicted `uncertain` (the spec's E3 asks for this): 0/175 = 0.00 (95% CI 0.00-0.02).

## Disagreements by detector reason

- met->no_threat:no_concrete_threat: 4
- missed->met:defended_other_loss: 2
- missed->no_threat:no_concrete_threat: 1
- missed->skipped:decided: 1
- uncertain->missed:all_checks_hold: 1

## Every disagreement (9)

| Item | Category | Label | Predicted | Detector outcome:reason | Move | Kind | Loss cp |
|---|---|---|---|---|---|---|---|
| mt2-015 | constructed_missed | missed | not_applicable | no_threat:no_concrete_threat | Rc8 |  |  |
| mt2-025 | met_real | met | not_applicable | no_threat:no_concrete_threat | Kxh4 |  |  |
| mt2-038 | constructed_missed | missed | not_applicable | skipped:decided | f4 |  |  |
| mt2-049 | adversarial | uncertain | missed | missed:all_checks_hold | Kf8 | capture | 252 |
| mt2-087 | met_real | met | not_applicable | no_threat:no_concrete_threat | Kg6 |  |  |
| mt2-103 | met_real | met | not_applicable | no_threat:no_concrete_threat | Rxd3 |  |  |
| mt2-104 | missed_real | missed | met | met:defended_other_loss | bxc5 | capture | 864 |
| mt2-121 | missed_real | missed | met | met:defended_other_loss | Qxd2 | fork | 435 |
| mt2-139 | met_real | met | not_applicable | no_threat:no_concrete_threat | Nxe1 |  |  |

## Reading these numbers

**Result in one line:** precision 84/85 = 0.99 (95% CI 0.94-1.00), recall 84/88 = 0.95 (CI 0.89-0.98). Both meet the targets
(0.90 and 0.85) as point estimates; the recall interval's lower end (0.89) also clears 0.85. The detector was not changed between the
v1 score and this one, and the set was frozen before it ran.

**What changed from v1 (recall 0.72):** the two v1 flaws were fixed in the set, not the detector: positions are now calm
(within 400 cp at depth 14 and 550 at depth 18), and `met` items need a concrete threat. Only 1 item is now skipped as decided
(was 41), and 4 `met` items (was 22) are called "no concrete threat". That supports the reading in the v1 notes that v1's low
recall came from the set. It is also a second look at the same detector by the same builder, so it is a fix to the test, not a
fresh independent confirmation.

**The 9 disagreements (read before quoting):**
- 4 `met` items called `no_threat` (`no_concrete_threat`): all `met_real`. The set accepts an engine line that wins 2 pawns within
  4 plies; the detector found no line that wins material or mates in its own replay. A difference in how the threat line is read,
  not yet looked at one by one.
- 2 `missed` items called `met:defended_other_loss` (mt2-104, mt2-121): the player's move stops the threat but loses 435 to 864 cp
  for another reason. The set labels them `missed` because the move ignores the puzzle's threat; ADR 0011 calls this a different
  mistake (often M1). The label may be arguable; I have not changed it (the set is frozen).
- 2 constructed `missed` items: one `no_concrete_threat`, one skipped as `decided` at depth 18.
- 1 adversarial item labelled `uncertain` was called `missed` (mt2-049, Kf8, loss 252 cp, threat kind capture). Either the label is
  wrong (the trapped-knight position may allow a move that saves the piece) or the pass cost is at least 150 cp so the rule for
  "unavoidable" does not apply. I did not check this one in depth.

**Not shown.** The set has one `uncertain` item, so it cannot judge `threat_unavoidable` or `loss_not_stable`; the detector never
predicted `uncertain` here (0 of 175). Nobody has reviewed the labels. Puzzle positions are tactically dense, so these numbers show
detection accuracy, not how often a player ignores a threat. v2 has 24 real `met` items instead of 40 because the lower rating bands
ran short.

**Next.** The real test is the hand-check page on the owner's games (M3d, gate 27 of 30 real flags), then the baseline run (M3e).

