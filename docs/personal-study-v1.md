# Personal study v1: did training change my real games? (draft, owner decides the open items)

Date: 2026-11-07 · Owner: Karthik Raman · Builds on ADR 0019, ADR 0002 (baseline window), ADR 0006 (PRD v2 rates) · Replaces "validate with 15 strangers" while the only user is the owner.

## 1. Question

Does a fixed amount of training reduce my rate of the mistakes I choose as targets in my real Chess.com rapid games, beyond the improvement I was already making?

Not claimed: that the product works for other people, or that it raises rating.

## 2. What we already know (descriptive, 584 usable games, July to November 2026)

- Median rating of each block of 100 games: about 407, 366, 421, 509, 555, 665, 690. Win rate by block: 46, 44, 56, 50, 52, 52, 56 percent. **I was improving before any training, so a before-and-after comparison alone proves nothing.**
- Position after move 10: ahead 236 games (75 lost), level 154 (72 lost), behind 194 (122 lost). Squandered advantages are 28% of losses; 45% are lost from a bad position.
- Detectors name a cause for about a third of squandered advantages, mostly a hung piece.

## 3. Design: interrupted time series with a frozen baseline

1. **Pre-trend (before anything starts).** Run the detectors over all synced games (`evidence_run`, about an hour) and compute my target rates for each block of 50 games since July. This shows the slope I was already on.
2. **Baseline.** The frozen window from ADR 0002 (100 rapid games, 10|0 and 15|10 kept separate) and its frozen results. Not changed.
3. **Intervention (fixed in advance, section 5).**
4. **Post windows.** Consecutive blocks of 50 games after training starts, per time control, using the same detector versions, engine config and floors as ADR 0006 (at least 20 games and 20 opportunities).
5. **Decision rule, written now (simple on purpose).** A target rate counts as improved when the post-start block is below the baseline rate **and** below the previous block, in two blocks in a row. The pre-trend is shown beside it as context, not as the test: with about 7 noisy blocks and a rate that cannot fall below zero, extrapolating it is too weak. This is one person with no blinding (builder and subject are the same): it shows direction, not proof. Intervals treat moves as independent and are optimistic (as `patterns.py` states); say so when reporting.
6. **Start date.** Set only when everything the study needs is built and the owner approves this plan (the day is then written here). Until then the owner keeps practising and playing as usual. Games before the start date, including the roughly 140 played since the baseline froze on 2026-10-07 while Practice and Replay were in use, are exploratory and never count toward the conclusion.

## 4. Outcomes

| Role | Measure | Why |
|---|---|---|
| Primary (proposal) | Hung own pieces per 100 player moves (M1) | Built, hand-checked (19 of 20), fast to move |
| Primary (proposal) | Missed free pieces, missed ÷ available (M2) | Same |
| Secondary | Share of games behind (-0.5 or worse) after Black's 5th move (early collapse) | 35% of losses start behind at this checkpoint (41% level, 25% ahead, 618 games); detectors skip before ply 8, so descriptive only |
| Secondary | Conversion rate (won ÷ ahead at the checkpoint, +0.5 or better) | Directional only: 117 of 196 so far (60%); about 40 ahead games a month at my pace |
| Reported every block | Share of positions excluded (uncertain or skipped by the detectors) | If improving changes how often positions are excluded, the rate moves for a reason that is not improvement. A large change in this share is a warning, and the block is read with care |
| Check, after 6 blocks | Do games with fewer hung pieces actually win more? | M1 and M2 are what the detectors can measure, not necessarily what costs games. If fewer hung pieces do not go with more wins, the primary outcome is the wrong target |
| Never primary | Rating, raw win rate | Too noisy and already trending up |

## 5. Intervention (proposal; owner sets dose)

Replay My Mistakes (P3) on my M1 and M2 positions, a set number of sessions per week, plus the delayed 72-hour unassisted tests (P4a). Practice is assisted and never counts as evidence (ADR 0005). Log: sessions, minutes, anything else I study (courses, videos, other apps), because outside study confounds the result.

**Dose is fixed and locked at the start date** (proposal: 4 sessions a week of 15 minutes). The dose is a guess, so the plan states in advance how to read the outcome:
- Dose kept (at least 80% of planned sessions logged) and no improvement under the rule after 6 blocks: **a null result for this intervention at this dose.** Change the intervention in a new pre-registered window.
- Dose not kept (under 80% logged): **inconclusive, not a null result.** Do not conclude the training does not work.
- Improvement under the rule with the dose kept: report it as direction in one person, with the exploratory games and study log beside it.

## 6. Sample and timing

About 33 games a week: a 50-game block is about 10 days; a 100-game window about 3 weeks. Win rate would need roughly 400 games per window to detect a 10-point change, which is why it is not primary. Plan for 3 post blocks (about 150 games, 5 weeks) before the first look, 6 blocks before a conclusion. Nothing is concluded from one block.

## 7. Threats and how each is handled

| Threat | Handling |
|---|---|
| Already improving | Pre-trend comparison (section 3) |
| Regression to the mean (starting after a bad run) | Baseline is the frozen window, not chosen by me |
| Opponent strength drifting up as my rating rises | Record opponent rating per block; report it beside the rates |
| Time-control mix changes | Report 10|0 and 15|10 separately (ADR 0002) |
| Other learning | Study log; note it in the report |
| Detector or engine change | Versions pinned; a change starts a new window |
| Peeking and choosing the metric afterwards | Outcomes and the decision rule are fixed in this file before the first post block |

## 8. If it does not work

After 6 blocks with no change against the rule: change the intervention, not the metric, and start a new pre-registered window. Record the negative result in an ADR.

## 9. Where I first fall behind (descriptive, 197 games at -1.0 or worse after move 10; depth-10 pass)

First move number where the engine rated my position -1.0 or worse for me: move 1: 2, move 2: 19, move 3: 28, move 4: 31, move 5: 27, move 6: 27, move 7: 15, move 8: 17, move 9: 11, move 10: 20. Cumulative: 41% by move 4, 68% by move 6, 90% by move 9.
- **My own move caused it in 192 of 197 games** (the opponent's move in 5). The median swing at that move was about 2.4 pawns.
- **The detectors do not look before ply 8** (White's 5th move), so the 80 games where I first fell behind by move 4 are outside M1 and M2.
- **I was Black in 130 of the 197 and White in 67**; I have not yet compared that with how often I play each colour.
- **Noise:** 351 of 592 games dipped to -1.0 or worse at some point by move 10, and 154 of those were back above -1.0 by move 11. A depth-10 dip is not always a real slip; the positions need the depth-18 check before they become drills.
- **Idea (owner):** use the position just before that first slip as the training starting position, a real position from my own game where I went wrong. It needs no cause label, only an engine-verified better move. It would be a new drill kind, with its own definition, version and hand-check.

## 10. Open items for the owner

1. Primary outcome: M1 only, M2 only, or both?
2. Dose: confirm 4 sessions a week of 15 minutes, or change it before it is locked.
3. Early collapse (45% of losses) is mostly a first-10-moves problem. Add the "before my first slip" drill kind (section 9) as a second intervention, or keep this study to M1 and M2?
4. Run the free competitor checks first (Aimchess report, Chess.com Insights) to decide build versus use.
5. Run the pre-trend now so the plan has a real slope.
6. The start date: set when everything the study needs is built.
7. Decided 2026-11-08: the checkpoint is after Black's 5th move with a ±0.5 threshold (ADR 0019 amendment). The descriptive tables in sections 2 and 9 of this plan are still at move 10 and are history. The checkpoint and threshold are now fixed for the study and must not change after the start date.
