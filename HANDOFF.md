# HANDOFF.md

Update this at the end of every session (any agent, any machine). Newest entry on top. Keep each entry short.

---

## Current state

- **Phase:** Week 1, Day 2 — T05, T06 done; T07 next
- **Active branch:** `feat/play-vs-stockfish` (PR into `main`)
- **Machine/agent last used:** MacBook / Claude Code
- **Baseline frozen?** No (planned Day 5 — do not use the coach on own games before this)
- **Frozen eval sets:** none yet

## Next up

1. Day 2: T07 Play/Practice flag in the UI (core already sets `assisted` permanently on switch; add a mode switch + API route).
2. Day 3: Chess.com sync (10|0 and 15|10 rapid); batch engine pass; one-game review.

## Blockers / open questions

- Confirm count of Chess.com 10|0 + 15|10 games available for the 100-game baseline.

---

## Log

### 2026-10-05 · MacBook · Claude Code (session 3)
- **Done:** T06. Play vs Stockfish: levels 1-10 (Skill Level 0-18), colour choice, resign, checkmate/draw end, PGN download. New `POST /games/{id}/engine-move` is idempotent. Fixed two web bugs found while testing in the browser (effect cancelled its own request; missing POST body sent a GET).
- **Next:** T07.
- **Blockers:** none. Opponent strength is unmeasured: Level n is a label, not an Elo.
- **Branch / PR:** `feat/play-vs-stockfish`

### 2026-10-05 · MacBook · Claude Code (session 2)
- **Done:** T05 `engine/stockfish.py` (Engine, Budget, Score, normalise); 7 tests, skipped if no Stockfish.
- **Next:** T06.
- **Blockers:** none.
- **Branch / PR:** `feat/engine-wrapper`

### 2026-10-05 · MacBook · Claude Code
- **Done:** T01-T04. `backend/` skeleton (uv, Python 3.12), `core/game.py` (legal moves, revision check, outcomes, resign, assisted flag, PGN export) with 13 tests; FastAPI game routes + shared `api/tools.py`; MCP `get_game` (mcp 2.x uses `MCPServer`, not `FastMCP`); Vite/React web board showing server-confirmed position (auto-queen promotion for now). Installed uv, pnpm, stockfish via brew (Stockfish 19 at /opt/homebrew/bin/stockfish).
- **Next:** T05 engine wrapper. Set `STOCKFISH_PATH=/opt/homebrew/bin/stockfish` in `.env`.
- **Blockers:** Docker not installed; not needed until Postgres/learner work. Game store is in-memory for now. Resign button and PGN download not yet in the web UI.
- **Branch / PR:** `feat/foundations`
