# missed_threat_v3, owner's check, round 1 (2026-10-30): gate not met, set not frozen

Mapping and gate as in LABEL_RULE.md (frozen before the page was shown): agreement of at least 20 of 24. **Result: 10 of 24.**
Answers: `check_round1_answers.txt` (the owner's, unedited). Key: `check_key.json` (git-ignored).

| Engine label | Owner's mapped label | Items |
|---|---|---|
| not_applicable | not_applicable | 5 of 5 agree |
| met | met | 3 of 5 (028, 041: owner saw no threat) |
| missed | missed | 2 of 8 |
| missed | not_applicable | 5 (023, 053, 060, 080, 083: owner saw no threat) |
| missed | met | 1 (011) |
| uncertain | met | 5 (003, 035, 037, 099, 100) |
| uncertain | missed | 1 (066) |

## Reading (checked on the positions after the answers; stated as findings, not as a score)
1. **Builder defect (mine): `uncertain` and `missed` do not check that the threat still works after the player's move.** The rule asked
   only that T be legal after M and that the engine score after M and T be low. In the five uncertain-vs-met items (and 011) the
   owner's B "no" fits: after the move the threat no longer wins by recaptures, and the loss comes from elsewhere. Those should be
   `met` (the detector's `defended_other_loss`), not `uncertain`. The owner was right on these.
2. **Seven "no threat" answers where the exchange count says there is one** (A "no" on 023, 028, 041, 053, 060, 080, 083). Four have
   a piece with no recapture at all (053 Qxh4, 060 Qxd5, 080 Nxf5, 083 Qxc6), two are a knight or bishop for a pawn (028, 041, 023). So
   the engine labels were right and the owner did not see the threat. That is the weakness the product measures; it also means a
   human under 1000 cannot be the oracle for "no threat". Two of these (knight for a pawn) may also be read as "a trade".
3. The five `not_applicable` items all agreed.

## Consequence
The set is **not frozen**. The 24 answers are used up as a check of the first labels. A changed rule is a new round: fix the builder
(point 1), rebuild, and show the owner a **new** 24 (different items), same mapping and gate. Point 2 is not "fixed" by relabelling
(that would be tuning to the owner); the gate for a "no threat" answer will be judged only where the builder's exchange count finds
no threat at all, with the 7 above reported as owner misses.
