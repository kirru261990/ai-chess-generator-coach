# 0020 · First-slip drill (2026-11-08)

Status: proposed. Define step of the build loop (`docs/workflow.md`); the owner answered the grilling questions Q1 to Q8 in chat on 2026-11-08. Nothing is built. Builds on ADR 0017 (drill library), ADR 0018 (drill cycles), ADR 0019 and `docs/personal-study-v1.md`.

## Why

68% of the owner's first big mistakes fall by move 10 (median move 8; 548 of 627 games have one, depth-10 pass, loss of at least 150 cp, ply 8 or later, position not already decided). The study (`docs/personal-study-v1.md` section 9) wants a drill from the position just before that mistake.

First Principles challenge, with the cheapest test of each assumption:

| Assumption | Status |
|---|---|
| A clear better move exists in most of these positions | Untested. Test: depth 18, three candidate moves, share where the best move clearly beats the second best. Part of the hand-check gate |
| Practising my own slip positions carries over to new games | **Weak as stated:** only 3 of 548 first-slip positions occur in another of the owner's games, so repeating one position trains memory of it. The drill therefore pairs own positions with fresh positions of the same kind (decisions 3 and 7) |
| The first slip is what loses the game | Untested. Earlier data: 154 of 351 early dips were recovered. The study measures outcomes, not this claim |
| The slips come early enough to train | Supported: median move 8, 68% by move 10 |

## Decisions

1. **A slip** is a move of the player at move 5 or later (ply 8 or later) that loses at least 150 cp for the player in a position that was not decided (under 600 cp either way), confirmed at the evidence config (Stockfish 19, depth 18, MultiPV 3, `ec-d46d6fec26ccdeb6`). The depth-10 pass only nominates candidates. If the best move is not clearly better than the second best, the position is skipped, not counted (rule 5). Slip-finder version `1`.
2. **A first-slip drill** is the position just before a game's first slip. One per game at most.
3. **Own and fresh drills.** Own drills come from the owner's games. Fresh drills come from running the same slip finder over the public Lichess games sample (both players rated 900 or lower), so they are real mistakes at the owner's level, engine-verified. No puzzle-book positions, and no generated positions in this version.
4. **Where it lives.** A third drill kind in the existing drill bank and the "Drill cycles" screen, beside hung-own-piece (M1) and missed-free-piece (M2). It reuses the attempt ledger, server timing, the assisted flag and the leak test from ADR 0018 (decisions 3, 6, 7). No new screen.
5. **Matched, not correct.** An answer matches when it is one of the engine's top moves within 50 cp of the best (three candidates, depth 18). Any other legal move is shown as "not one of the checked moves; the engine did not rule on it", never as wrong (ADR 0018 decision 4).
6. **A round** is ten positions, about 15 minutes: five own and five fresh. (The word "session" stays with Replay My Mistakes, five positions.) Before the answer the response holds the board, the side to move, the question and the legal moves only. After the answer the screen shows the move the owner actually played, the engine's line and what the slip lost; the game move is never shown beforehand.
7. **Own positions are asked once or twice, spaced** (py-fsrs scheduling, MIT, to be added to `THIRD_PARTY.md` first); fresh positions follow so the owner practises the pattern.
8. **Practice, so assisted** (ADR 0005, rule 4). Every attempt is stored `assisted=1` and never counts as evidence.
9. **Quality gate.** Before the drill is released the owner hand-checks 30 positions on the existing Yes / No / Can't tell page; each needs a clear "yes" to "the engine's move is clearly better, and I could have seen why". Gate: 27 of 30 (as in ADR 0006 and ADR 0013). Until then drills are labelled engine-verified, not human-checked.
10. **Versions stored with every drill:** slip-finder version, bank version, engine config, detector versions, drill-kind id (rule 6).

## Does this touch the study?

Yes, as part of the intervention, not as an outcome. From the start date the intervention is Replay My Mistakes plus this drill, at the same locked dose of 4 sessions or rounds a week of about 15 minutes (`docs/personal-study-v1.md` section 5). The study measures the package against M1, M2 and early collapse; it cannot separate this drill's effect from the rest. Results from the drill itself (matches, speed) are practice data and never evidence. Adding it before the start date does not change the pre-start blocks.

## What this does not show

- Matching the engine's move in a position you have seen is partly memory (ADR 0018). Fresh drills are the only part that tests the pattern, and even they are assisted.
- Counts of slips are yields from a filter, not error rates.
- The slip finder at depth 10 nominates candidates and can miss some; the confirmed set is not a complete list of the owner's first mistakes.
- The fresh sample covers players rated 900 or lower; whether it matches the owner's mistakes is part of the hand-check, not assumed.

## Reversal

Remove the third drill kind from the drill bank, the cycles screen and the slip finder module; the ledger rows stay (assisted, never evidence). Nothing else depends on them.

## Open before building

- `py-fsrs` licence row (MIT, version 6.3.2, Python 3.10 or later) in `THIRD_PARTY.md`.
- The size of the hand-check sample if 30 is too many (the owner did not want another 30-position check in ADR 0017 decision 9; this drill uses the 27-of-30 gate unless the owner changes it).
