# 0017 · Drill library from public Lichess games (2026-11-05)

Status: accepted by the owner in chat (2026-11-05); stage A built first, stage B (move-impact preview) later.

## Why

The product so far trains the owner on the owner's own games. The owner wants a middlegame tactics trainer that anyone can use, built from public data only (Lichess monthly games, CC0, plus Stockfish), with no player linking an account. This widens the scope in `docs/spec.md` (v0.4 section 11 puts monetisation after month 3; this ADR does **not** add any revenue feature, it only adds a second source of drills).

## Decisions

1. **Source:** Lichess standard rated games, Rapid, both players rated 500 to 1800, normal ending, at least 20 moves. Streamed from the monthly file with `evals/tools/lichess_stream_sample.py --low 500 --high 1800`; only the start of the month is read (stated in the sidecar JSON). Raw games stay in git-ignored `data/lichess/`. Lichess ratings rarely go below about 600, so the lowest band will be thin and is reported as it is.
2. **Rating tag:** every drill carries the average rating of the two players (`avg_rating`) so easy drills can be served first.
3. **Middlegame** (`drillbank.in_middlegame`): the position before the move is at half-move index 12 to 60, and each side has at least 3 pieces besides king and pawns. (The first proposal said "castled" and "4 pieces"; both were dropped because many players under 1200 never castle, and 3 keeps real middlegames with a queen trade.) Changed only on a set not yet scored, with a new bank version.
4. **What counts as a drill:** a position from a real game where the side to move made a move the existing detectors call a mistake: `M1` hanging own piece (`hanging_own` v4) and `M2` missed free piece (`missed_free` v3). Both players' moves are used, so every drill is "the position the player faced". The detectors, thresholds and evidence engine (pinned Stockfish 19, depth 18) are unchanged; uncertain results are dropped (rule 5).
5. **`M3` missed threat is off by default.** It failed its hand-check on the owner's games (23 of 30, ADR 0013) and is not validated on real play (ADR 0015). `--types M3` can produce experimental drills, labelled as such, but they are not part of the bank until M3 passes a check.
6. **Prefilter:** a shallow pass (depth 10) before and after each middlegame move keeps only moves that lose at least 100 cp for the mover; only those get the depth-18 detectors. This makes the build about ten times cheaper. **A consequence: drill counts are yields, not error rates**, and say nothing about how often players err (rule 3 is untouched because no rate is shown).
7. **Each drill stores** the position before the move (FEN), the move played, the detector's evidence record, the engine's verified better moves, the rating tag, the Lichess game id (a public id, no names), and the bank, detector, rules and engine versions (rule 6).
8. **Storage:** a separate git-ignored folder `data/drills/` (`drillbank_v1.jsonl` and its own engine cache). The owner's `data/coach.sqlite3` is not touched in stage A. Serving drills in Practice (a new pool) is a later step with its own schema change.
9. **Quality gate before release:** a sample is checked by the owner on the Yes / No / Can't tell page, size to be agreed (the owner does not want another 30-position check). Until then drills are labelled engine-verified, not human-checked.
10. **Stage B (later):** a "what happens if I move this piece" preview in Practice, computed by `python-chess` and Stockfish, Practice only (ADR 0005). Forcing lines (a chain of checks, captures and threats that wins material) are a proposed new motif for this stage; they need their own definition, detector and eval before they are shown, and are not promised until then.

## What this does not show

- Drill counts are not error rates and not evidence of anything about players.
- Detectors were scored on frozen Lichess sets and hand-checked on the owner's games only for M1 and M2; the 500 to 1800 band has not been checked above 1200.
- No claim that drills improve rating. Success is reported as correct out of attempted, with the random-guess level, as in PRD v2.

## Hand-check result, version 1 (2026-11-05): 16 of 20 real, gate 18 not met

The owner answered `drillcheck_v1` (10 hanging-own-piece, 10 missed-free-piece, one drill per game, ratings 800 to 1700). **M1: 9 of 10 real; M2: 7 of 10 real.** Not real: dc-07 (M1, B "can't tell"), dc-12, dc-17 and dc-18 (M2, A "no").

- All three M2 "no" answers are drills where the captured piece can be taken straight back (on d5, d5 and f3). `missed_free` v3 counts material along the engine's best line, so a capture that is recaptured still counts when the engine line shows a follow-up win (dc-12: Nxd5 exd5 Rxe7 wins the bishop the knight was defending). That is a real win, but it is not a free piece, and the page asked "could you take it and come out ahead".
- 32 of the 75 M2 drills in the 300-game bank (43%) allow an immediate recapture; 5 of the 10 sampled (dc-12, 15, 16, 17, 18). The owner said "yes" on 15 and 16, "no" on 12, 17 and 18, so the recapture alone does not decide it.
- **Decision (to confirm with the owner):** do not retune on these 20. Split M2 drills into "free" (nobody can retake it, or retaking loses more) and "wins after a follow-up" (a separate, harder kind with its own question wording), build a new check sample, and keep M1 as it is. This is a drill-library rule, not a change to `missed_free` v3 or to the owner's PRD v2 rates.
- Raw result: `data/drills/drillcheck_v1_result.json` (git-ignored). The v1 sample is used and not reused.

## Timing classes (2026-11-05, after the version 1 check)

A missed-free-piece drill is now labelled by **how many of your moves it takes to be ahead**, so the question can say it plainly.
"Ahead" = at least 3 points more than at the start (pawn 1, knight or bishop 3, rook 5, queen 9), counted after the engine's best
reply to your last move, for **every** way they can take the piece back. `app/learner/drilltiming.py`, engine replies from the pinned
evidence engine (depth 18, cached).

| Class | Meaning | Question wording |
|---|---|---|
| `right_away` | ahead after the capture and their best retake (1 move) | "Could you win material right away? ... Even if they can take it back, you are then at least 3 points ahead." |
| `next_move` | ahead after your second move: you capture, they retake, your next move wins something | "Could you win material on your next move? ..." |
| `within_3_moves` | ahead after your third move | "Could you win material within your next 3 moves? ..." |
| `unclear` | not ahead within 3 moves along the engine's best replies | left out of the drill set |

- **Bank, 75 missed-free-piece drills:** right away 38, next move 29, within 3 moves 2, unclear 6.
- **Against the owner's version 1 answers on the same 10:** right away 5 of 5 "yes", next move 2 of 2 "yes", within 3 moves 0 of 1 (dc-17 "no"), unclear 0 of 2 (dc-12, dc-18 "no"). **This sample designed the rule, so it is not a test of it**; version 2 is the test.
- **Correction:** in chat, dc-12 was first described as winning a bishop and ending 3 points ahead. The engine line continues 1.Nxd5 exd5 2.Rxe7 Rxc6, so the net is bishop for pawn, 2 points: `unclear` under the 3-point rule. The classifier caught what a hand count missed.
- **Check version 2** (`drillcheck` VERSION 2): 10 hanging-own-piece drills and 10 missed-free-piece drills (5 right away, 4 next move, 1 within 3 moves; only 2 of that class exist and one was used in version 1), none from version 1, one per game, `unclear` never shown. Gate 18 of 20.

## Hand-check result, version 2 (2026-11-05): 19 of 20 real, gate 18 met

The owner answered `drillcheck_v2` (10 hanging-own-piece, 10 missed-free-piece with timing classes: 5 right away, 4 next move, 1 within 3 moves; none from version 1). **M1: 9 of 10 real; M2: 10 of 10 real.** Not real: dc-01 (M1, A "yes", B "no").

- The timing classes and per-class wording fixed the version 1 failures: every M2 drill was a real "win material within N moves" for the owner.
- Caveats: 20 positions, one reviewer, ratings up to about 1700; M2 `within_3_moves` has one sample and only 2 drills exist in the 300-game bank. `unclear` drills were not shown, so they stay excluded. Drills are now "engine-verified and owner-checked on 40 positions (two checks)", not a rate claim.
- Raw result: `data/drills/drillcheck_v2_result.json` (git-ignored).

## Reversal

Delete `data/drills/` and the `drillbank` module; nothing else depends on them. The `--low` / `--high` options of the sampler default to the old 600 to 1200.
