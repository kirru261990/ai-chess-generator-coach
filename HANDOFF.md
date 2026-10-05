# HANDOFF.md

Update this at the end of every session (any agent, any machine). Newest entry on top. Keep each entry short.

---

## Current state

- **Phase:** Week 1, Day 3 done — Day 4 (detectors) next
- **Active branch:** `feat/batch-analysis` (PR into `main`)
- **Machine/agent last used:** MacBook / Claude Code
- **Baseline frozen?** No (planned Day 5 — do not use the coach on own games before this)
- **Frozen eval sets:** none yet

## Next up

1. Day 4: T11 `hanging_own` v1 detector + 50 labelled positions; T12 `missed_free` v1 + 50; T13 precision/recall script.
2. Day 5: T14 run detectors over the baseline window; T15 freeze baseline; T16 blind-spot map page.

## Blockers / open questions

- ~~Baseline game count~~ resolved: 450 case-study games available (253 at 10|0, 197 at 15|10), 4 Jul – 5 Oct 2026. Enough for a 100-game baseline; the window still needs choosing before Day 5 freeze.
- Fast-pass evaluations are not yet flagged as uncertain when unstable (spec B2); needs a second-depth comparison.
- Reviews are not cached; each call re-runs the deep check (a few seconds).

---

## Log

### 2026-10-05 · MacBook · Claude Code (session 5)
- **Done:** T08 Chess.com sync (`uv run python -m app.sync`, 450 games into `data/`); T09 count (above); T10 fast pass over all 450 games (`uv run python -m app.engine.batch`, ~5 min at depth 10, Stockfish 19) and `GET /synced-games/{id}/review` (up to 3 moments, deep-checked at depth 16). Spot-checked one real game: findings were sensible.
- **Next:** T11 `hanging_own` detector with 50 labelled positions, then T12, T13.
- **Blockers:** none. `.env` holds the username and contact email (git-ignored, not committed).
- **Branch / PR:** `feat/batch-analysis`

### 2026-10-05 · MacBook · Claude Code (session 4)
- **Done:** T07. `POST /games/{id}/mode`; web mode selector, switch button with confirmation, assisted badge. Hints, scan prompts and takebacks do not exist yet; the flag is in place for when they do.
- **Next:** T08 Chess.com sync.
- **Blockers:** need `CHESSCOM_USERNAME` and a contact email for the User-Agent in `.env`.
- **Branch / PR:** `feat/play-practice-flag`

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
