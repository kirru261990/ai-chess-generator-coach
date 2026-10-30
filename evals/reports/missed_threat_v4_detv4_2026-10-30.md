# missed_threat_v4: M3 detector scores (2026-10-30)

Set: frozen `missed_threat_v4` (positions.jsonl sha256 `d96bdf74cc563c6d...`). Detector: `missed_threat` v4 with Stockfish 19 at depth 18 (labels used depth 14 separately). Targets fixed before the run: precision >= 0.9, recall >= 0.85. Positive class = `missed`. Every figure is `successes/denominator` with a 95% Wilson interval. Nothing was tuned on this set.

**All items: precision 27/27 = 1.00 (95% CI 0.88-1.00) (meets the target as a point estimate); recall 27/30 = 0.90 (95% CI 0.74-0.97) (meets the target as a point estimate).**

## Precision and recall for `missed`

| Group | Precision (TP / predicted missed) | Recall (TP / labelled missed) | Exact agreement |
|---|---|---|---|
| all items | 27/27 = 1.00 (95% CI 0.88-1.00) | 27/30 = 0.90 (95% CI 0.74-0.97) | 82/88 = 0.93 (95% CI 0.86-0.97) |
| real positions (real play: missed_real, met_real, hung_not_threat, quiet_blunder) | 27/27 = 1.00 (95% CI 0.88-1.00) | 27/30 = 0.90 (95% CI 0.74-0.97) | 82/88 = 0.93 (95% CI 0.86-0.97) |

## Exact agreement by item category

| Category | Agreement |
|---|---|
| met_clean | 13/15 = 0.87 (95% CI 0.62-0.96) |
| met_other_loss | 13/14 = 0.93 (95% CI 0.69-0.99) |
| missed | 27/30 = 0.90 (95% CI 0.74-0.97) |
| not_applicable | 29/29 = 1.00 (95% CI 0.88-1.00) |

## Confusion matrix, all items (label -> predicted: count)

met->met: 26, met->not_applicable: 3, missed->met: 2, missed->missed: 27, missed->not_applicable: 1, not_applicable->not_applicable: 29

Predicted `uncertain` (the spec's E3 asks for this): 0/88 = 0.00 (95% CI 0.00-0.04).

## Disagreements by detector reason

- met->no_threat:no_concrete_threat: 2
- missed->met:defended_other_loss: 2
- met->skipped:already_lost: 1
- missed->no_threat:no_concrete_threat: 1

## Every disagreement (6)

| Item | Category | Label | Predicted | Detector outcome:reason | Move | Kind | Loss cp |
|---|---|---|---|---|---|---|---|
| mt3-016 | met_clean | met | not_applicable | no_threat:no_concrete_threat | Kxf2 |  |  |
| mt3-023 | met_clean | met | not_applicable | skipped:already_lost | Qe8 |  |  |
| mt3-035 | missed | missed | met | met:defended_other_loss | Qe7 | fork | 352 |
| mt3-074 | met_other_loss | met | not_applicable | no_threat:no_concrete_threat | Qxd6 |  |  |
| mt3-082 | missed | missed | not_applicable | no_threat:no_concrete_threat | Rad1 |  |  |
| mt3-085 | missed | missed | met | met:defended_other_loss | Qe7 | other | 525 |
