# hanging_own_v1: labelled positions (DRAFT, not frozen)

50 positions for the `hanging_own` detector: 25 `missed`, 25 `taken`.
Each row of `positions.jsonl` is a FEN before the move, the move played, and a label.

## Where the positions come from

Weak, blunder-prone Stockfish self-play (Skill Level 0, plus a random move 25% of
the time), seed `20261005`, 7 games, at most 5 / 3 / 2 positions per game for
missed / hard-negative / ordinary. No player data is involved.
Rebuild with `cd backend && uv run python ../evals/tools/build_hanging_own_set.py`.

## How the labels were made

Labels are **engine-derived, not human**. Stockfish 19 at depth 12 analyses the
position before and after the move, and the material count is followed along the
engine's best line (up to 6 plies). This is independent of the detector's static
exchange check.

- `missed`: the engine's best reply is a capture, the line loses at least 2 pawns of
  material for the mover, and the evaluation drops at least 100 cp versus best play
- `taken`: no material loss of 2 or more, and an evaluation drop under 100 cp
- Anything in between (108 of 336 scanned positions) is ambiguous and excluded.
  The set therefore covers clear cases only.

`taken` rows are 15 hard negatives (a piece moved onto an attacked square, or a
capture) and 10 ordinary moves.

## Known weaknesses: read before quoting any number

1. **The label rule was changed once after looking at the detector's output on this
   set.** A broad first definition counted forks and other non-capturing refutations
   as `missed`; I restricted it to "best reply is a capture". The detector itself was
   not changed. Scores on this set are therefore optimistic. Before publishing
   precision/recall, evaluate on a **fresh set built with a new seed and a frozen label
   rule** (T13).
2. Labels have not been reviewed by a person. Spot-check a sample, then record the
   review here.
3. Positions are weak-engine play, which is more blunder-heavy and tactically
   simpler than real games under 1000. They are not a sample of real play.
4. A `missed` label means "the engine says material is lost to a capture", not "a
   piece was left on an undefended square". The two overlap but are not identical.

## Detector change since this set was built

`hanging_own` went from v1 to v2 (legal captures only; an external review of
`missed_free` exposed a pinned-attacker defect that v1 shared). On this set, `missed`
calls were 20 of 22 correct with 20 of 25 real misses found under v1, and 21 of 23 and
21 of 25 under v2: one position changed. The set has no position built to test pins, so
it cannot tell whether v2 is right in general. The regression tests do that. These are
smoke checks on a set whose labels were refined once after viewing results; do not quote them.

## Status

Draft. Not frozen. `HANDOFF.md` lists no frozen sets; update it when this changes.
