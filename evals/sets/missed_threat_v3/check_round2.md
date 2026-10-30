# missed_threat_v3, owner's check, round 2 (2026-10-30): gate not met again (15 of 24), set not frozen

Gate and mapping as in LABEL_RULE.md and Amendment 1: at least 20 of 24. **Result: 15 of 24** (round 1: 10 of 24).
Answers: `check_round2_answers.txt`. Key: `check_key_r2.json` (git-ignored).

| Engine label | Items | Agree with the owner | Where they differ |
|---|---|---|---|
| not_applicable | 5 | 5 | none |
| met (clean 1, other_loss 4) | 5 | 4 | 067: owner saw no threat |
| missed | 8 | 6 | 063: owner saw no threat (a mate in one, Qh4#); 014: owner said the move also loses something else (D) |
| uncertain | 6 | **0** | 003, 026 (a piece hangs with no recapture) and 035: owner saw no threat; 037: owner said no other move helps (C no, left unmapped); 066: owner said the move stops it (see below); 082: owner A to D = missed |

## Reading (after the answers; findings, not tuning)
1. **`missed`, `met` and `not_applicable` agree on 15 of 18 (83%).** The three misses are owner misses of a threat (063, 067) or a D
   judgement (014). Every "owner saw no threat" item has a threat the exchange count finds (a mate in one on 063, hanging pieces on 003 and
   026).
2. **`uncertain` cannot be checked by the owner: 0 of 6.** Its label rests on the engine (a big loss that the forced threat does not
   explain), and the owner's four questions cannot show that: D asks about "something else" and the owner can only judge what they see.
   Two items show the builder is also blind in places: on 066 (Bb5 pins the queen) the owner was right that the threat no longer works, and
   the builder's exchange count ignores the pin; on 082 (fxg3 attacks the queen on h4) the same kind of tactic decides it.
3. So the gate fails mainly because of one label class and a handful of unseen threats, not because of a general disagreement.

## Not decided (owner)
Whether to freeze the 85 non-`uncertain` items (a rule change after two rounds of results, so labelled as such) and test the `uncertain`
behaviour another way (a small hand-built set or the first hand-check's cases), or run another round, or drop v3.
