**Read this before quoting any figure.**

**What these numbers are.** How accurately the two detectors classify moves on 202 frozen items: 180 real positions taken from
Lichess puzzles (with a few hand-checked reviews behind them) and 22 positions built by hand to break the detectors. Nothing was
tuned on this set; the detectors and the set were not changed after the first run. The spec's E3 targets (precision at least 90%,
recall at least 80%) are met by the point estimates for both detectors, with and without engine evidence. For `hanging_own`
the lower end of the 95% interval for static precision (0.85) is below 0.90, so "met" there is a point estimate, not a guarantee.

**What these numbers are not.**
1. **They are not how often anyone makes these mistakes**, and not how the detectors will perform on ordinary games. Puzzle
   positions are curated tactics, so opportunities are far denser than in normal play.
2. **High agreement here partly reflects a shared definition.** The set's labels come from an independent search that uses the
   same material definition the detectors implement ("a legal capture that nets at least two pawns after best recaptures").
   Agreement shows the detectors implement that definition correctly (pins, recaptures, legality). It does not show that the
   definition captures what matters in a game.
3. **`missed_free` has no real "missed" examples in the set.** Puzzles only show correct solutions, so every `missed` item for
   `missed_free` is constructed (40 misses plus adversarial). Precision and recall for `missed` on real positions are therefore
   `n/a (0 cases)`; on real positions only `taken` and `not_applicable` were tested (60 of 60 agree). **Recall of real, ignored free
   pieces is unmeasured.**
4. **Intervals are wide for the small groups.** The 9 adversarial `hanging_own` items and the real mate-theme splits carry little
   weight on their own.
5. **Labels have had limited review:** 82 of 202 items, by a checker under 1000 and by GPT; no strong human player has checked
   the set (see `FROZEN.md`).

**The four disagreements are three items, and none is a logic error in a detector.** All are about how sensitive the engine
evidence is:
- **rp1-080** (labelled `uncertain`; static says `missed`): White is being mated whatever it plays (loss 0), so the right outcome
  is `uncertain`. Static, by design, cannot know that. With evidence the detector gets it right. This is the intended
  behaviour, shown as a static-only "error".
- **rp1-095** (labelled `uncertain`; both modes say `missed`): the label's engine run (depth 14) measured a loss of 98 cp, just
  under the 100 cp threshold; the scoring run (depth 10) measured 237. The item sits on the threshold, so a small change of search
  depth flips the outcome.
- **rp1-128** (a hand-built `hanging_own` miss; evidence mode says `uncertain`): White is already far ahead (about +5), and at depth 10
  the engine reports no loss from giving up the knight (524 after versus 519 before), while the label's depth-14 run measured 106.
  **When a position is already lopsided, engine evidence under-reports a hung piece, so the pipeline abstains**. That is
  correct under the abstain-rather-than-guess rule, but it means real misses in already-won or already-lost positions will be
  counted as `uncertain`, not `missed`. Expect that on real games.

**Uncertain rate (E3 asks for it):** see the line under each confusion matrix.

**Do not use any figure here as a baseline or as evidence that coaching works.** The next step (T14) runs the detectors on the
owner's real games; those numbers are rates with denominators and do not depend on this set.
