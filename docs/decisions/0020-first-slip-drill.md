# 0020 · First-slip drill (2026-11-08)

Status: accepted; backend built on `feat/first-slip-drill` (2026-11-08), web screen and spaced review not built yet. Define step of the build loop (`docs/workflow.md`); the owner answered the grilling questions Q1 to Q8 in chat on 2026-11-08. Builds on ADR 0017 (drill library), ADR 0018 (drill cycles), ADR 0019 and `docs/personal-study-v1.md`.

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

1. **A slip** is a move of the player at move 5 or later (ply 8 or later) that loses at least 150 cp for the player in a position that was not decided (under 600 cp either way), confirmed at the evidence config (Stockfish 19, depth 18, MultiPV 3, `ec-d46d6fec26ccdeb6`). The depth-10 pass only nominates candidates. The before and after searches are independent, so if the played move is also one of the accepted answers they disagree and the position is `unclear`. **Clear answer rule (built, refines the first wording):** the position is skipped as `unclear`, not counted (rule 5), when any of the three engine lines is 50 to 100 cp worse than the best, because it is then not clear whether that move counts as an accepted answer. (The first wording, "best clearly better than the second best", contradicted decision 5, which accepts near-equal moves.) An `unclear` first slip ends the search in that game: a later slip would not be the first. Boundaries: a line at most 50 cp worse is accepted, a line more than 50 and under 100 cp worse is `unclear`, a line 100 cp or more worse is clearly not accepted. Slip-finder version `1`.
2. **A first-slip drill** is the position just before a game's first slip. One per game at most.
3. **Own and fresh drills.** Own drills come from the owner's games. Fresh drills come from running the same slip finder over the public Lichess games sample (both players rated 900 or lower; `slipbank --max-rating`, default 900, drops other games and games without ratings), so they are real mistakes at the owner's level, engine-verified. No puzzle-book positions, and no generated positions in this version.
4. **Where it lives (as built).** Its own file of drills (`data/drills/slips_v1.jsonl`, `app.learner.slipbank`), its own round ledger (`data/drills/slip_rounds.sqlite3`) and routes `GET /drills/rounds/current`, `POST /drills/rounds/current/answer`. It follows ADR 0018 (server timing, assisted flag, leak test, matched-not-correct) but is separate from the frozen 50-drill cycle set, so the owner's cycle-1 baseline stays comparable. The web screen is a later step and needs the Design step first.
5. **Matched, not correct.** An answer matches when it is one of the engine's top moves within 50 cp of the best (three candidates, depth 18). Any other legal move is shown as "not one of the checked moves; the engine did not rule on it", never as wrong (ADR 0018 decision 4).
6. **A round** is ten positions, about 15 minutes (a guide: nothing in the code bounds the time; if fewer than five drills of one source are left, the other source tops it up, and fewer than ten usable drills is an error): five own and five fresh. (The word "session" stays with Replay My Mistakes, five positions.) Before the answer the response holds the board, the side to move, the question and the legal moves only. After the answer the screen shows the move the owner actually played, the engine's line and what the slip lost; the game move is never shown beforehand.
7. **Own positions are asked once or twice, spaced** (py-fsrs scheduling, MIT, to be added to `THIRD_PARTY.md` first); fresh positions follow so the owner practises the pattern. **Not built yet:** this version asks every drill once and never repeats a drill in a later round.
8. **Practice, so assisted** (ADR 0005, rule 4). Every attempt is stored `assisted=1` and never counts as evidence.
9. **Quality gate.** Before the drill is released the owner hand-checks 30 positions on the existing Yes / No / Can't tell page; each needs a clear "yes" to "the engine's move is clearly better, and I could have seen why". Gate: 27 of 30 (as in ADR 0006 and ADR 0013). Until then drills are labelled engine-verified, not human-checked.
   **Replaced 2026-11-09 (owner):** a player under 1000 cannot judge an engine's move by eye, so the 30 positions are checked by the engine itself at depth 24 (the drills were built at 18), from scratch: the slip must still lose at least 150 cp and the deeper best move should be an accepted one (`slipverify`, same gate of 27 of 30 on the slip). Result on the 30 sampled positions: 29 of 30 slips hold, 30 of 30 answer sets hold; the one that did not (1.3 pawns, just under the line) is excluded from rounds (`slip_excluded_v1.json`). This is the same engine at a deeper search, a strong second opinion and not independent proof; the full 382 were not run. The human Yes / No page was built, then removed as superseded.
10. **Versions stored with every drill:** slip-finder version, bank version (the record layout), engine config; the drill kind is the type `S1`. There is no detector version because this drill uses no motif detector. The drill id includes the slip-finder version and the resume key does too, so a new version re-scans every game and writes new records; only drills of the current finder version and bank layout are served (older ones stay in the file as history), and a position already used in a round is not offered again under a new id.

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
