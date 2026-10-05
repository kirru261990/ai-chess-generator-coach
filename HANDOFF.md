# HANDOFF.md

Update this at the end of every session (any agent, any machine). Newest entry on top. Keep each entry short.

---

## Current state

- **Phase:** Week 1, Day 4 in progress — T11 done, T13 next
- **Active branch:** `feat/hanging-own-detector` (PR into `main`)
- **Machine/agent last used:** MacBook / Claude Code
- **Baseline frozen?** No (planned Day 5 — do not use the coach on own games before this)
- **Frozen eval sets:** none yet

## Next up

1. Day 4: T13 precision/recall script, evaluated on FRESH seeded sets with frozen label rules (see the two set READMEs for why the current drafts are optimistic). Include some real-game positions if possible.
2. Day 5: T14 run detectors over the baseline window; T15 freeze baseline; T16 blind-spot map page.

## Blockers / open questions

- ~~Baseline game count~~ resolved: 450 case-study games available (253 at 10|0, 197 at 15|10), 4 Jul – 5 Oct 2026. Enough for a 100-game baseline; the window still needs choosing before Day 5 freeze.
- Fast-pass evaluations are not yet flagged as uncertain when unstable (spec B2); needs a second-depth comparison.
- Reviews are not cached; each call re-runs the deep check (a few seconds).

---

## Log

### 2026-10-05 · MacBook · Claude Code (session 9)
- **Done:** T12. `detectors/missed_free.py` (v1) and a 50-position draft set (`evals/sets/missed_free_v1/`, builder `evals/tools/build_missed_free_set.py`). Also web: engine reply is shown 1 s after the player's move (`ENGINE_MIN_REPLY_MS`). Takeback rule confirmed by the user: 2 undos per move (a new move resets the allowance), which is what is implemented.
- **Smoke check only:** 24/24 `missed` calls correct, 24/25 misses found on the draft set. The set is easy; do not quote.
- **Next:** T13.
- **Blockers:** none. Both draft sets need a human spot-check of labels.
- **Branch / PR:** `feat/missed-free-detector`

### 2026-10-05 · MacBook · Claude Code (session 8)
- **Done:** user feedback. (1) Click-to-move replaces drag and drop (PR on `feat/click-to-move`; the API now returns `legal_moves` for highlighting). (2) Practice-mode Undo, at most 2 in a row, via `POST /games/{id}/takeback`; `Game.revision` is now a monotonic counter; stacked on the click-to-move branch, so merge that PR first.
- **Decision to confirm:** "at most 2 previous steps" was implemented as 2 undos in a row (a new move resets the allowance), not 2 per game. Change `MAX_TAKEBACKS` / the reset in `core/game.py` if a per-game cap was meant.
- **Next:** T12.
- **Branch / PR:** `feat/practice-takeback`

### 2026-10-05 · MacBook · Claude Code (session 7)
- **Done:** fixed the web app showing "Cannot reach the API" when Vite ran on a port other than 5173 (the API's CORS only allowed 5173). It now allows any `localhost` / `127.0.0.1` port; other origins stay blocked, with a test. Restart a running backend to pick it up (no `--reload`).
- **Next:** T12.
- **Branch / PR:** `fix/cors-local-dev-ports`

### 2026-10-05 · MacBook · Claude Code (session 6)
- **Done:** T11. `detectors/see.py`, `detectors/hanging_own.py` (v1), 50-position draft set built by `evals/tools/build_hanging_own_set.py`. Quick check on that set: 20 of 22 detector `missed` calls correct, 20 of 25 real misses found (~91% / 80%), but see the set README: labels were refined once after viewing detector output, so do not quote these.
- **Repo moved** out of the `Claude workshops` folder to `~/Projects/ai-chess-generator-coach` so the unrelated `26c8015_AI_Agent` repo cannot see it. Virtualenv and node_modules were rebuilt there.
- **Next:** T12, then T13.
- **Blockers:** none. Labels in the set are engine-derived and need a human spot-check.
- **Branch / PR:** `feat/hanging-own-detector`

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
