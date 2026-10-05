# HANDOFF.md

Update this at the end of every session (any agent, any machine). Newest entry on top. Keep each entry short.

---

## Current state

- **Phase:** Week 1, Day 1 done — next is Day 2 (Play)
- **Active branch:** `feat/foundations` (PR into `main`)
- **Machine/agent last used:** MacBook / Claude Code
- **Baseline frozen?** No (planned Day 5 — do not use the coach on own games before this)
- **Frozen eval sets:** none yet

## Next up

1. Day 2: Play vs Stockfish (levels, colour, resign, PGN export); Play/Practice flag.
2. Day 3: Chess.com sync (10|0 and 15|10 rapid); batch engine pass; one-game review.

## Blockers / open questions

- Confirm count of Chess.com 10|0 + 15|10 games available for the 100-game baseline.

---

## Log

### 2026-10-05 · MacBook · Claude Code
- **Done:** T01-T04. `backend/` skeleton (uv, Python 3.12), `core/game.py` (legal moves, revision check, outcomes, resign, assisted flag, PGN export) with 13 tests; FastAPI game routes + shared `api/tools.py`; MCP `get_game` (mcp 2.x uses `MCPServer`, not `FastMCP`); Vite/React web board showing server-confirmed position (auto-queen promotion for now). Installed uv, pnpm, stockfish via brew (Stockfish 19 at /opt/homebrew/bin/stockfish).
- **Next:** T05 engine wrapper. Set `STOCKFISH_PATH=/opt/homebrew/bin/stockfish` in `.env`.
- **Blockers:** Docker not installed; not needed until Postgres/learner work. Game store is in-memory for now. Resign button and PGN download not yet in the web UI.
- **Branch / PR:** `feat/foundations`
