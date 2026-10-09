# ADR 0005 — Practice assistance: what helps, when, and what it must never do

**Status:** Accepted 2026-10-09 · **Decided by:** the owner, while practising (his requests, in order), on Claude's proposals
**Related:** AGENTS rule 4 (Practice is not assessment), spec A3

## The rule
Anything that helps the player is **assistance** and exists **only in Practice**, where the game is marked `assisted` for good. In
Play (which counts as real evidence) none of it may exist or stay visible. One check enforces this in the page
(`feedbackToShow` in `web/src/gameState.ts`) and the server refuses the assistance endpoints in Play with 403
(`feedback`, `threats`, `eval`, `coach/why`).

## What the owner decided (all reversible, each is a few lines)
| Decision | Reason | To reverse |
|---|---|---|
| **Undo is unlimited** in Practice, back to the start; the earlier cap of two in a row (session 8) is reversed | "Let the user undo any number of moves; let's not restrict it" | Reintroduce a counter in `core/game.py` (`take_back`) and `can_take_back` |
| **Left arrow key = Undo** (not while typing or in a menu) | Faster practice | Remove the key handler in `web/src/App.tsx` |
| **An evaluation bar** beside the board replaces "this cost you X pawns" | The pawn cost was hard to track | Hide `EvalBar`; `GET /games/{id}/eval` can stay |
| **The better move is never shown on its own.** After a suboptimal move a 💡 icon appears; pressing it shows the position before the move on the main board with a green arrow | "Don't be proactive; let the user play, then show what could have been best." The suggestion is only valid for the earlier position, so it is shown on that position, not on the live board | Draw the arrow directly (it would point at wrong squares once the opponent replied) |
| **Marks on the board** after a slip, mistake or blunder: your piece that can be taken (red, kept on the square where it was taken) and a free piece you missed (green) | Facts the verdict text states, shown where they are | Remove `boardMarks` |
| **A badge on the moved-to square**: 📖 book, ★ best, 👍 good, ?! inaccuracy, ? mistake, ?? blunder | "Like how Chess.com does it" | Remove the `squareRenderer` badge (keep the board styles, see below) |
| **Starter opening book** of about 60 lines for "book" | No opening list on disk; avoided downloading without permission | Replace `LINES` with the CC0 lichess-org/chess-openings tables (T43) |

## Known traps
- `react-chessboard` **skips its own square styling** (move dots, marks, hint tint) when a custom `squareRenderer` returns an element;
  the renderer must apply the shared `boardStyles` itself (a source guard test checks this).
- Do not switch branches in the folder a running dev server serves while the owner is practising; use a `git worktree`.

## Open questions for the owner
1. Should the best-move arrow also appear automatically after a suboptimal move? It stays behind the 💡 for now.
2. Should the start-position evaluation (about +0.3 for White) be shown as equal?
3. Download the CC0 opening tables for a full book (about 0.5 MB)?
