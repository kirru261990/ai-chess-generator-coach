# missed_threat_v4, first score of `missed_threat` v3: notes (read before quoting any number)

**Result:** precision 27/27 (1.00, 95% CI 0.88 to 1.00), recall 27/30 (0.90, CI 0.74 to 0.97), exact agreement 83/88 (0.94). Both targets
(0.90 and 0.85) are met **as point estimates only**: the lower ends are 0.88 and 0.74. The set was frozen before the detector ran
(FROZEN.md). v3's rule was written before the set was built (ADR 0014) and the set's labels use the same independent builder as `missed_threat_v3`.
Nothing was tuned on this set. The report file is named 2026-10-31 (the scorer stamped it 2026-10-30 by the machine's local day).

## What this does and does not show
- **It is not shown that v3 beats v2.** v2 scored 0.96 / 0.93 on `missed_threat_v3`, v3 scores 1.00 / 0.90 on `missed_threat_v4`: different sets,
  overlapping intervals. The one thing it does show is that the false-positive pattern that v2 got wrong (an even trade after a move that guards
  the piece) did not recur: 27 predicted `missed`, 27 correct.
- Same limits as v3 set: not a rate of ignored threats (quota-built), static capture or mate threats only, the exchange count (in labels and in
  the detector's first test) does not see pins or mating attacks, 24 of 88 items checked by a person (22 of 24 agree), the owner had help
  on one board, real Lichess games at 600 to 1200 from the start of one month. No `uncertain` class (see the v3 set's notes).
- The labels and the detector share an idea (does the threat still win after the move), in different code at different depths.

## The five disagreements (leads, not verdicts)
- **Two `missed` items called `met` (mt3-035, mt3-085: `defended_other_loss`, both ...Qe7).** The detector now says the move stops the threat; the
  builder says it does not. This is the cost of v3's engine-played check: when the engine's line after the threat shows no net material in four
  plies, a real gain that comes later is read as "stopped". Worth a look: if both are real misses, v3 trades false positives for false negatives.
- **One `missed` item called `no_threat` (mt3-082):** the owner saw no threat either (the item the owner's check kept as an owner miss); the
  detector's depth-18 pass search finds no concrete threat.
- **Two `met` items called `no_threat` (mt3-016, mt3-074):** the depth-18 pass search finds nothing concrete where the depth-14 builder did. No effect on precision.

## Next
M3 may still not be shown as a weakness (ADR 0011 (d)): the detector now has a passing score on two sets, but the second condition is a new
owner hand-check on real Chess.com games with the new wording, gate 27 of 30. Then the real-game rates (TASKS M3e). Not done: the hand-check, the
`uncertain` behaviour on real cases, mt3-035 and mt3-085.
