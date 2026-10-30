# missed_threat_v3: M3 detector scores (2026-10-30)

Set: frozen `missed_threat_v3` (positions.jsonl sha256 `4379cbf96ebf8c49...`). Detector: `missed_threat` v2 with Stockfish 19 at depth 18 (labels used depth 14 separately). Targets fixed before the run: precision >= 0.9, recall >= 0.85. Positive class = `missed`. Every figure is `successes/denominator` with a 95% Wilson interval. Nothing was tuned on this set.

**All items: precision 27/28 = 0.96 (95% CI 0.82-0.99) (meets the target as a point estimate); recall 27/29 = 0.93 (95% CI 0.78-0.98) (meets the target as a point estimate).**

## Precision and recall for `missed`

| Group | Precision (TP / predicted missed) | Recall (TP / labelled missed) | Exact agreement |
|---|---|---|---|
| all items | 27/28 = 0.96 (95% CI 0.82-0.99) | 27/29 = 0.93 (95% CI 0.78-0.98) | 77/84 = 0.92 (95% CI 0.84-0.96) |
| real positions (real play: missed_real, met_real, hung_not_threat, quiet_blunder) | 27/28 = 0.96 (95% CI 0.82-0.99) | 27/29 = 0.93 (95% CI 0.78-0.98) | 77/84 = 0.92 (95% CI 0.84-0.96) |

## Exact agreement by item category

| Category | Agreement |
|---|---|
| met_clean | 13/15 = 0.87 (95% CI 0.62-0.96) |
| met_other_loss | 7/10 = 0.70 (95% CI 0.40-0.89) |
| missed | 27/29 = 0.93 (95% CI 0.78-0.98) |
| not_applicable | 30/30 = 1.00 (95% CI 0.89-1.00) |

## Confusion matrix, all items (label -> predicted: count)

met->met: 20, met->missed: 1, met->not_applicable: 3, met->uncertain: 1, missed->met: 2, missed->missed: 27, not_applicable->not_applicable: 30

Predicted `uncertain` (the spec's E3 asks for this): 1/84 = 0.01 (95% CI 0.00-0.06).

## Disagreements by detector reason

- met->no_threat:no_concrete_threat: 3
- missed->met:defended_other_loss: 2
- met->uncertain:threat_line_diverged: 1
- met->missed:all_checks_hold: 1

## Every disagreement (7)

| Item | Category | Label | Predicted | Detector outcome:reason | Move | Kind | Loss cp |
|---|---|---|---|---|---|---|---|
| mt3-031 | met_other_loss | met | not_applicable | no_threat:no_concrete_threat | Bb5+ |  |  |
| mt3-042 | met_clean | met | not_applicable | no_threat:no_concrete_threat | Rxh5 |  |  |
| mt3-044 | missed | missed | met | met:defended_other_loss | Qf5+ | capture | 1007 |
| mt3-048 | met_other_loss | met | uncertain | uncertain:threat_line_diverged | b5 | capture | 638 |
| mt3-049 | met_other_loss | met | missed | missed:all_checks_hold | Qe7 | capture | 478 |
| mt3-059 | met_clean | met | not_applicable | no_threat:no_concrete_threat | Nxe5 |  |  |
| mt3-095 | missed | missed | met | met:defended_other_loss | d5 | other | 386 |
