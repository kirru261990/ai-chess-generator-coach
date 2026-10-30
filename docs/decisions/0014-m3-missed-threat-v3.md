# 0014 — M3 `missed_threat` v3: let the engine play both sides when asking "does the threat still work?"

Status: detector built 2026-10-31; eval set `missed_threat_v4` and its owner check still to do. Decided by: Claude (the owner may change it).
Builds on ADR 0013. v2 stays in the repository history; v2's score on `missed_threat_v3` (0.96 / 0.93) is not changed by this.

## Problem (found in v2's first score, `evals/reports/missed_threat_v3_2026-10-30_notes.md`, item mt3-049)
v2 decided "the threat still works after the player's move" by replaying the **pass line**. Its player replies were chosen for the passed
position, so a defender that appears with the move is missing: after ...Qe7 guarding the bishop on c5, Bxc5 Qxc5 is an even trade, yet the
replay (Bxc5 d6, with no recapture) showed a free bishop. The forced-threat loss of ADR 0013 then agreed, because it measures the drop from the
best move, which also contains a winning chance the player threw away. Result: an even trade was called a missed threat (a false positive).

## v3 rule
After the player's move M, play the threat move T and let the evidence engine choose **both** sides' replies from there (`forced_threat`).
The threat still **works** when any of these holds, counted for the opponent:
1. T is a capture and the exchange count (`see.capture_net`, after the best recaptures) nets at least `M3_MATERIAL_MIN`;
2. the line T + the engine's best line (at most `MAX_REFUTATION_PLIES`) nets at least `M3_MATERIAL_MIN` or mates;
3. the engine reports a mate in at most `M3_MATE_MAX_MOVES` for the opponent, or T itself mates.
Otherwise it is **stopped**. The exchange count (1) comes first because an engine line cut at four plies stops in the middle of an exchange
(the Ruy Lopez bishop on a4: a real engine run showed 1 net after four plies although the bishop is simply lost).
The same call gives the forced-threat loss of ADR 0013 (no extra search). `threat_line_diverged` is gone: with the engine playing both sides
there is no stale reply to diverge on. `threat_unavoidable` uses the same check after the best move. `VERSION` = "3"; the thresholds are unchanged.

## Not solved
Pins, discovered attacks and anything else the exchange count cannot see still count as a stopped threat when neither the exchange count nor
a four-ply engine line shows a gain. The forced-threat loss still compares against the best move, so it can credit a threat with a loss that
came from a squandered advantage when the threat also nets material; only the "still works" question was fixed here.

## Evaluation
v3 is **not** scored on `missed_threat_v3` (that set exposed the flaw; scoring a fix on it would be tuning on it). A new frozen set,
`missed_threat_v4`, is built from Lichess positions not used before, with the same independent builder and label rule, an owner check with the
blue-arrow page (gate 20 of 24), and then one score with the targets of ADR 0011 (precision 0.90, recall 0.85).

## Reversal
Set `VERSION` back to "2" and restore `threat_after_move`; v2 and v3 rows are told apart by `detector_version` (`evidence_run retire`).
