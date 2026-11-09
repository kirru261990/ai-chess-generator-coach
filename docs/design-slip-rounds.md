# Design note: the slip round screen (2026-11-09)

Design step of the build loop for ADR 0020 and ADR 0021. Agreed with the owner in chat on 2026-11-09. Mode: Operate (a task screen). Look and feel follow `DESIGN.md` and the Drill cycles tab; nothing new is invented.

## Job

Ten positions at the owner's real game pace. Find the better move before the clock runs out, then see why on the board, then name the habit.

## Where

A new tab, **Slip rounds**, next to Drill cycles. Drill cycles stays as it is (its 50 drills are the cycle-1 baseline). Practice, so always assisted.

## Flow

1. **Start.** Three timer buttons: 15 s (default, "your average in a 10-minute game"), 8 s, No timer. The choice is remembered and fixed per position when it is first shown.
2. **Question.** The existing app board (react-chessboard), side to move at the bottom, click a piece then a square, as in Drill cycles. A thin bar under the board drains left to right, with the seconds beside it. Amber at 3 s left, no flashing. At 0 it says "Over time" and stays; the board stays usable and a late answer still counts. Reduced motion: the bar steps once a second. Shown before the answer: board, side, question, legal moves, timer. Nothing else (leak rule).
3. **Review (after the answer).** Matched or not (never "wrong"), time, over time or not. Then the line on the board:
   - Two tabs, **Your move** and **Better move**, each a line of up to 6 moves (3 for each side) from the engine, stepped with **Next move** and **Back**, plus **Play** (runs it on its own, tap to pause).
   - The latest move is a bold arrow, earlier ones fade. Colours as on the 30-position page: red = your move, green = better move, orange = their reply. No move numbers.
   - A caption names the move ("They: pawn takes queen on d5") and a running tag shows the points ("You −8 points", or "Level").
   - Under the board: the cause label and the one-line habit. Neutral colour, so it does not read as a verdict. `other` says there is no reason to give and shows no habit.
4. **Next position.** One button.
5. **End of round.** Matched x of 10, over time x of 10, middle time, and "Practice, not evidence". Rates keep their denominators.

## Data the screen needs (all after the answer)

`lines.mine` and `lines.better`: for each, the start FEN and up to 6 steps `{uci, san, who, points}` where `points` is your running material change in points. Engine lines are computed once per drill and stored beside the drills (`slip_lines_v1.json`); the answer route only reads them.

## Not in the first version

Per-cause match rates and cause-weighted rounds; phone layout (undecided in `PRODUCT.md`); lines longer than 6 moves; arrows on the board during the question.

## Accessibility

Buttons are real buttons with visible focus; arrow keys step the line; the tag and caption carry the meaning, not colour alone.
