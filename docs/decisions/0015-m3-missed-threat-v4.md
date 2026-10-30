# 0015 · M3 `missed_threat` v4 (2026-10-30)

Status: built; **not validated on the owner's games**. Follows ADR 0013 (hand-check version 3 failed, 23 of 30) and ADR 0014.

## Rules added

1. **Already lost** (`M3_LOST_LIMIT_CP` = 400): if the player's best score before the move is below -400, the position is skipped (`already_lost`). Seen in m3c-19 (-508 before, the best move -509 after).
2. **The best move must neutralise the threat:** before `missed`, play the threat after the engine's best move (`forced_threat`). If the threat still works and the engine's score after it is at least `M3_EVAL_LOSS_CP` below the score before, the outcome is `uncertain/threat_unavoidable` (the player's move was only worse against a threat nothing stopped). Recorded as `best_move_ftl`. Seen in m3c-21.

`VERSION` = "4". Rows from v3 are retired by `evidence_run retire`.

## Scores (frozen Lichess sets, engine labels plus owner checks of the sets; the detector never ran on the owner's games)

| Set | precision | recall |
|---|---|---|
| `missed_threat_v3` (84) | 26/26 = 1.00 (95% CI 0.87-1.00) | 26/29 = 0.90 (0.74-0.96) |
| `missed_threat_v4` (88) | 27/27 = 1.00 (0.88-1.00) | 27/30 = 0.90 (0.74-0.97) |

For comparison v3 on the v4 set was 1.00 / 0.90, so v4 changes nothing there. Reports: `evals/reports/missed_threat_v3_detv4_2026-10-30.*`, `missed_threat_v4_detv4_2026-10-30.*`.

## What this does and does not show

- v4 does not break anything on the Lichess sets. That is all these numbers show.
- The two rules were fitted to two of the seven hand-check misses, so they say nothing about whether v4 would pass the hand-check. The other five (only-move defences, counter-attack defences, an opened-file trade) are untouched.
- **The owner will not do another hand-check and the detector is not to be run on the owner's games again.** ADR 0011 (d)'s second condition therefore stays unmet: M3 is not shown as a weakness and the real-game rates (TASKS M3e) stay blocked unless the owner decides otherwise.

## Reversal

Set `VERSION` back to "3" and remove the `already_lost` gate and the `best_move_ftl` block in `detect`.
