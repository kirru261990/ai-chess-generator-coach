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
   - Two tabs, **Your move** and **Better move**, each a line of up to 6 moves (3 for each side) from the engine, stepped with **Next move** and **Back** only. No autoplay and no GIF: the owner chooses when to move on (2026-11-09).
   - The latest move is a bold arrow, earlier ones fade. Colours as on the 30-position page: red = your move, green = better move, orange = their reply. No move numbers.
   - A caption names the move ("They: pawn takes queen on d5"), a running tag shows the points ("You −8 points", or "Level"), and under it one **why** sentence for the step, built only from the detector's own record (see below).
   - Under the board: the cause label and the one-line habit. Neutral colour, so it does not read as a verdict. `other` says there is no reason to give and shows no habit.
4. **Next position.** One button.
5. **End of round.** Matched x of 10, over time x of 10, middle time, and "Practice, not evidence". Rates keep their denominators.

## Data the screen needs (all after the answer)

`lines.mine` and `lines.better`: for each, the start FEN and up to 6 steps `{uci, san, who, points}` where `points` is your running material change in points. Engine lines are computed once per drill and stored beside the drills (`slip_lines_v1.json`); the answer route only reads them.

## The why behind each move (decided 2026-11-09, built after the tab)

One plain sentence per step, from a fixed template filled with facts a detector recorded. It names the exact piece and square; "stops their threat" alone is too vague.

- **Ignored threat** (threat kinds already in `threat_kind.py`): `mate` "They threaten checkmate with the queen to h7." · `capture` "They threaten to take your bishop on e5 with the knight." · `fork` "They threaten a fork: the knight to f7 attacks your queen and rook." · `discovered` "Moving their bishop would uncover an attack on your queen." · `other` "They threaten to win material with the knight to d4." The better move then says how it stops it, by geometry: moves the attacked piece away, defends it, takes the attacker, or blocks the line.
- **Hanging piece:** "After this, they can take your knight on f3 with the pawn." The better move: "This keeps the knight safe (it is defended / it moves away)."
- **Missed free capture:** "You could take their rook on d5 with the queen, and nothing can take it back." The better move: that capture.
- **Other:** no sentence. The line and the points still show; no reason is invented.

### Arrows that go with the why (owner, 2026-11-09)

Each why sentence draws what it talks about on the board, so the sentence and the picture say the same thing:

- **Orange arrow:** their move, the threat or the capture they can make ("the knight takes the bishop on e5").
- **Red arrow** for your played move, **green arrow** for the better move, same colours as the stepper.
- **Yellow square** on the piece in danger or the piece you could take (the detector's `target_squares`).
- When the sentence says how the better move stops a threat, both arrows show together: orange for the threat, green for your answer. A move that defends draws its arrow to the defended square; a move that blocks draws it onto the line between the attacker and the target.
- Squares and moves come from the detector's own record, never from the wording. Without a detector record there is no sentence and no extra marks, only the stepper's own arrows.

## Not in the first version

Per-cause match rates and cause-weighted rounds; phone layout (undecided in `PRODUCT.md`); lines longer than 6 moves; arrows on the board during the question.

## Accessibility

Buttons are real buttons with visible focus; arrow keys step the line; the tag and caption carry the meaning, not colour alone.
