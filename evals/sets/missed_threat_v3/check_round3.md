# missed_threat_v3, owner's check, round 3 (planned 2026-10-30; written before the answers)

LABEL_RULE.md is frozen, so this note carries the change instead of an amendment there ("Amendment 3"). It checks the frozen set; it does not
edit it, and it cannot change its labels or its hashes. It exists to test whether the engine labels hold when the owner's own tactical
blind spots are taken out of the question, which rounds 1 and 2 could not separate.

## What went wrong in rounds 1 and 2 (the tally)
Round 2, 9 disagreements out of 24: 6 on the `uncertain` class (the owner cannot judge it; the builder also missed pins), 2 where the owner
missed a threat (a mate in one; hanging pieces), 1 on D ("does the move lose something else"). So 20 of 24 was out of reach by design: with
`uncertain` in the sample, at most 18 items were judgeable. On the other three classes the owner agreed on 15 of 18 (83%).

## What round 3 changes
1. **No `uncertain` items** (they are not in the frozen set) and **no D question** (it only separated `uncertain` from `missed`).
2. **Every board shows the opponent's best reply after a pass as a BLUE arrow**, for every item, including those with no threat, so the
   arrow does not reveal the label. The owner is asked whether that blue move wins material, not to find it. A, B, C as before.
3. **24 frozen items never shown before** (8 missed, 8 met, 8 not_applicable).

Mapping (unchanged, minus D): `missed` = A yes, B yes, C yes. `met` = A yes, B no. `not_applicable` = A no. Gate: **at least 20 of 24
agree.** If it is met, the exception recorded in FROZEN.md (gate not met in rounds 1 and 2) is answered for the three scored classes;
the `uncertain` class stays apart either way. If it is not met, the labels are reported with all three rounds and nothing is re-run to
reach 20.
