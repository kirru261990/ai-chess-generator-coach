# missed_free_v1: labelled positions (DRAFT, not frozen)

50 positions for the `missed_free` detector: 25 `missed`, 15 `taken`, 10 `not_applicable`.
Each row of `positions.jsonl` is a FEN before the move, the move played, and a label.

## Where the positions come from

Weak, blunder-prone Stockfish self-play (Skill Level 0, plus a random move 25% of the
time), seed `20261006`, 9 games, at most 5 / 3 / 2 positions per game for missed /
taken / not_applicable. Only positions where the side to move had a capture of a
non-pawn piece were considered. No player data is involved.
Rebuild with `cd backend && uv run python ../evals/tools/build_missed_free_set.py`.

## How the labels were made

Labels are **engine-derived, not human**. Stockfish 19 at depth 12 analyses the position
before the move, and the material count is followed along the engine's best line (up to
6 plies). This is independent of the detector's static exchange check.

- opportunity: the engine's best move captures a non-pawn piece and its line gains at
  least 2 pawns for the mover
- `taken`: opportunity, the player captured a non-pawn piece, and the evaluation drop
  versus best play is under 100 cp
- `missed`: opportunity, the player did not capture a non-pawn piece, and the
  evaluation drop is at least 100 cp
- `not_applicable`: no opportunity per the engine, although the mover could capture a
  *defended* non-pawn piece (a hard negative for the detector)
- Anything else (53 of 291 scanned positions) is ambiguous and excluded. The set covers
  clear cases only.

## Known weaknesses: read before quoting any number

1. Labels have not been reviewed by a person. Spot-check a sample, then record the review here.
2. Positions come from weak-engine play, where free pieces are plentiful and obvious.
   This set is **easy** compared with real games under 1000, so scores on it will look
   better than real-game performance.
3. Unlike `hanging_own_v1`, the label rule was **not** changed after viewing results on
   this set, and the detector was not tuned to it. A first look found 24 of 24 `missed`
   calls correct and 24 of 25 real misses found; treat that as a smoke test, not a result.
   The detector was then changed once because of an external review (GPT, PR #12), which
   found two defects (a losing capture credited as "taken", and a pinned attacker creating a
   free piece). The same 24/24 and 24/25 came out after the fix. **That means this set has
   no position that exercises either bug**, so it is too easy to catch this kind of error.
   The fresh set for T13 must include adversarial cases: pinned capturers, captures that
   lose material, and several capturers of different values on one target.
4. Before publishing precision/recall, evaluate on a **fresh set built with a new seed**
   (T13), ideally including positions from real games.
5. "Free piece" here excludes pawns and requires a legal capture; the detector and the
   oracle agree on that scope by design.

## Status

Draft. Not frozen. `HANDOFF.md` lists no frozen sets; update it when this changes.
