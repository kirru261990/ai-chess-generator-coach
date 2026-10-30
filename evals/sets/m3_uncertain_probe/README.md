# m3_uncertain_probe (not frozen, not human-checked)

A small probe of the `uncertain` outcomes of `missed_threat` (v3), which no score covers. **Engine-labelled only**; read it as a rough
check, not a score. Built by `evals/tools/build_uncertain_probe.py build`, scored by `... run` (writes `result.json`).

- **unavoidable (20):** positions from Lichess games not used in `missed_threat_v3`/`v4`, where a static threat exists, passing costs
  under 100 cp and the threat still works after the engine's best move. Expected: `uncertain:threat_unavoidable`.
- **not_from_threat (15):** the 15 unfrozen candidates in `missed_threat_v3/uncertain_unverified.jsonl` (the move loses, the threat does
  not explain it). Expected: `uncertain:loss_not_from_threat`.

## Result for detector v3 (2026-10-30)

| Group | n | as expected | other outcomes |
|---|---|---|---|
| unavoidable | 20 | 6 | 11 `no_concrete_threat`, 3 `passing_costs_little` |
| not_from_threat | 15 | 6 | 4 `no_concrete_threat`, 4 `defended_other_loss`, **1 `missed`** (up-028) |

No unavoidable-threat position became `missed` (the other outcomes stay out of the rate). One position from the second group (up-028)
was called `missed`; it is unchecked by a human, so it may be a label error or a false positive. The builder cannot see pins, so some
"no concrete threat" cases may be label errors too.
