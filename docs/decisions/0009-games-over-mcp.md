# 0009. Play and assisted-practice games against Stockfish in chat (MCP)

Date: 2026-10-17 · Status: accepted · Builds on ADR 0007 (practice over MCP), ADR 0008 (the board as an MCP app), ADR 0005 (practice assistance)

## Context
ADR 0007 said "Practice only": the tools were Replay My Mistakes. The owner now wants the web app's Play tab in chat too: a game
against Stockfish, either **Play** (no help, counts as real evidence) or **Practice (assisted)** (verdicts, badges, hints, undo,
threat arrows). The hard constraint is AGENTS rule 4 / ADR 0005: everything that helps the player exists only in Practice and must
not reach a Play game anywhere: not in the tool results, not in the structured data, not in the widget.

## Decision
1. **Seven game tools** over the existing shared tool layer `app/api/tools.py` (the same one the web API uses; no chess or engine logic of
   our own, rule 1). Names use the `game_` prefix next to the `practice_` ones.

   | Tool | Annotation | Modes | Notes |
   |---|---|---|---|
   | `game_new(color, level, mode)` | write | both | `color` white/black, `level` 1 to 10, `mode` play/practice. Stockfish opens if the player is Black. |
   | `game_move(game_id, move, expected_revision?)` | write | both | `move` as SAN (`Nf3`, `O-O`) or UCI (`g1f3`); the engine's reply is part of the call. |
   | `game_show(game_id)` | write | both | Safe to repeat. If Stockfish owes a reply (its search failed after your move was saved) it plays it, so a stuck game recovers. |
   | `game_resign(game_id)` | write | both | |
   | `game_undo(game_id)` | write | practice only | Marks the game assisted (it already is). |
   | `game_hint(game_id, level)` | write | practice only | The hint ladder, steps 1 to 5. Records how many positions needed a hint. |
   | `game_threats(game_id, show)` | write | practice only | Turns the threat arrows on or off for the game (default on, as in the web app). |

   There is **no tool that switches mode**. A game ends in the mode it started in. (The web app can switch Play to Practice; that is
   not offered in chat, and "switch back" would be the worse direction anyway: Practice to Play must never be possible.) Starting a test or
   a baseline stays impossible (ADR 0007 decision 1).
2. **Where games live.** The MCP server is a separate process from the FastAPI one. Games sit in an in-memory dict in each process
   (`app.api.store.GAMES`), so **the chat's games and the web app's games do not see each other, and both vanish when their process
   restarts** (Postgres, T30, would change that). The MCP server keeps **its own registry**: it reuses the same in-memory dict (the
   tool layer needs it) but also records which game ids *it* created and refuses any other id, so a tool can only act on a game
   started through the connector. At most 20 games are kept; starting a 21st drops the oldest. Nothing is written to the store: a chat game is
   not saved, has no review and enters no progress number. That is a limit, and the docs say so in plain words.
3. **Rule 4 enforcement, by construction.**
   - Play results are built from an explicit allow-list of keys (`PLAY_KEYS`: id, fen, moves, revision, turn, user_color, mode,
     engine_level, outcome, legal_moves). Practice adds one nested `practice` object (assisted flag, hints used, can-take-back, the
     threat toggle, threats, the feedback on the last move, a hint). Nothing is copied by "everything except".
   - The help tools check the mode on the server (the shared layer already refuses with `feedback_not_allowed`,
     `takeback_not_allowed`); they return a refusal sentence and no data in Play.
   - The tool text for a Play game is only status, the move record (SAN) and the letter board; no verdict, no evaluation, no
     "best" or "threat" wording. A regression test scans every Play payload (structured and text) for forbidden keys and words.
   - The widget draws help only from `payload.practice`, and ignores it unless `game.mode === 'practice'`. In Play it renders the board,
     a one-line status and a Resign button.
4. **The widget is the same `board.html`** (one `ui://` resource, one file). The tool result carries `kind: "game"`; the page picks the
   Replay page (`Practice.tsx`, payload `{view, summary}`) or the new game page (`GameBoard.tsx`, payload `{kind: "game", ...}`).
   `GameBoard.tsx` talks to a `GameBackend` interface (like `PracticeBackend`); `gameToolBackend(call)` turns each step into a tool
   call. It reuses the pure helpers of `gameState.ts` (move badges, board marks, threat arrows, hint visibility, end banner). The web
   app's `App.tsx` is not changed.
5. **Left out on purpose (first version).** The evaluation bar and "Why?" (the coach model call, with spend) are not in chat; the
   verdict, badge, marks, hint ladder, threats and undo are. No PGN download (the sandbox cannot save files); the move record is in the text.
6. **Server instructions** say that the model only relays: it never says whether a move is good, suggests a move, or mentions threats or
   evaluation in a Play game, and calls `game_hint` only when the player asks. **This is guidance, not enforcement.** The model can
   see the board in the text and in the widget's data and may still comment; the server cannot stop that. What the server does
   guarantee is that no *help data* is sent for a Play game. A Play game with unsolicited model comments is not an unassisted test either way
   (nothing here is a test), and the owner should treat chat Play as casual play. Real unassisted evidence stays in the web app.

## Not changed
No test or baseline tool; no new dependency; auth, tunnel and the practice tools as in ADRs 0007 and 0008.

## Reverse
Delete `app/mcp/game_tools.py` and the `game_*` tools in `server.py`; the widget keeps working for practice (the page falls back to
the Replay page).

## Addendum 2026-10-17: the player's move shows first
The owner saw the move appear 1 to 2 seconds late, together with Stockfish's reply, because `game_move` does both in one call. The web app shows
the move at once and the reply no sooner than 1 s later. So the board page now uses two more tools marked `_meta.ui.visibility = ["app"]`:
`game_apply_move(game_id, move, expected_revision)` (only the player's move, returned at once, with no verdict: the verdict needs an engine
search, so it comes with the next step) and `game_engine_move(game_id, expected_revision)` (the reply; it plays only if it is the engine's
turn and the game is still at that revision, so a stale or double call never plays a second move). `game_move` is unchanged for text-only
clients (one call, both moves). The page also tints the last move. The same rule 4 gating applies: the data comes from the same builder.

`visibility: ["app"]` is only metadata the **host** may honour; the server still lists these tools. Whether Claude hides them from the model is
not known, so their descriptions and the server instructions say "never call them". Guidance, not enforcement, as before.
