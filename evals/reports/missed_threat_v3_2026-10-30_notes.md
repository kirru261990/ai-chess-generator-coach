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
