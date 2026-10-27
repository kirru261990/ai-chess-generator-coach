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
