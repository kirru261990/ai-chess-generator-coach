# missed_threat_v4: label rule (written before any detector ran on the set)

Same rule as `missed_threat_v3/LABEL_RULE.md` including its Amendment 1 (the threat must still win after the player's move, by the exchange
count; a move that stops the threat but loses for another reason is `met` with `met_kind = other_loss`), with these differences:
1. **No `uncertain` class.** v3's `uncertain` items could not be checked by a person (0 of 6) and the builder's exchange count is blind to pins;
   they are not built. Detector `uncertain` outcomes count as "not missed" when scoring, as in v3 (its Amendment 2).
2. **Quota:** 30 `missed`, 30 `met` (15 clean, 15 other_loss: more moves that defend or stop the threat but lose elsewhere, the pattern v2 got
   wrong), 30 `not_applicable`. Seed `20261101`. Games already used by `missed_threat_v3` are skipped.
3. **Source:** a larger sample of the same Lichess file (`lichess_stream_sample.py --games 9000`), the start of 2026-09, rated Rapid, both 600 to 1200.
4. **Owner's check** (before freezing): 24 items (8 missed, 8 met, 8 not_applicable), each board with the opponent's best reply after a pass drawn
   in blue for every item (v3's round 3 page: questions A, B, C; `missed` = A yes, B yes, C yes; `met` = A yes, B no; `not_applicable` = A no).
   **Gate: at least 20 of 24 agree.** An item the owner contradicts is removed unless it is an A "no" where the exchange count finds a threat
   (an owner miss). If the gate is not met the set is not frozen and nothing is re-run to reach it.

## Why a new set
`missed_threat` v3 (ADR 0014) fixes a flaw v2's score on `missed_threat_v3` exposed. A fix must not be scored on the set that exposed it.

## Scoring (fixed before the run)
`missed_threat` v3 with the evidence engine (depth 18), `score_missed_threat.py --set missed_threat_v4`. Positive class `missed`; precision >= 0.90 and
recall >= 0.85 with 95% Wilson intervals; every disagreement listed. Nothing is tuned on the set; report next to v2's score on `missed_threat_v3`, not
instead of it. Limits as for v3: static threats only, the exchange count does not see pins, 24 items checked by a person, 600 to 1200 Lichess games.
