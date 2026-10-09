# AI Chess Coach

> Work in progress — built in public.

A chess coach that plays, analyses, finds your recurring tactical misses, and coaches you with explanations that are **checked against the engine before you see them**. Progress is measured in your real games, not just puzzles.

## Why

Players under ~1200 lose most games to the same misses — hanging pieces and missed threats. Engine reviews flag the move but not the pattern, AI explanations are sometimes confidently wrong, and nothing shows whether training changed anything.

## What it does

- **Play** against Stockfish (Maia-2 human-like opponent planned)
- **Analyse** games played here or synced from Chess.com (Lichess and PGN import planned)
- **Find patterns** as rates with denominators, per time control, against a frozen baseline of your own games
- **Coach** with explanations that are checked against the engine and rules before you see them
- **Practise** with per-move feedback and threat warnings, always marked "assisted"

## How it fits together

```
Web app (board, review, blind spots)                 MCP server (skeleton)
              \                                          /
               +------------- FastAPI + shared tool layer -----------+
                                  |
     chess core (python-chess, owns all state)    Stockfish    detectors (versioned)
                                  |
                  coach harness: evidence -> draft -> verify -> one repair -> checked facts only
```

The backend owns chess state. The language model never decides what is legal, never counts, and never states a tactical
claim that has not been checked (a claim verifier plus a guard on the text). If a check fails twice, you get only the facts
the engine and rules confirmed, with a note.

## Where it is today

| Works | Not yet |
|---|---|
| Play vs Stockfish (click to move, Level 1-10, resign, PGN download) | Training sessions and hint ladder |
| Practice mode: Undo, an evaluation bar beside the board, a verdict after each move (good / slip / mistake / blunder), what was right or wrong, a 💡 hint that draws a green arrow for a stronger move only when you ask (a suggestion only), "Watch out" threat warnings; always marked assisted | Lichess sync, PGN import, Maia-2 opponent |
| Chess.com sync, batch engine analysis, post-game review (up to 3 key moments) | Postgres persistence (games live in memory), sign-in, other users |
| Review tab: say what you were thinking at a key moment and see what was really on the board (your words saved as written) | Peer benchmark (needs a Lichess games sample) |
| Detectors `hanging_own` and `missed_free` (versioned), run over a frozen 100-game baseline; a Blind spots page with 10\|0 and 15\|10 side by side | Forks and pins; recency windows and example links on the map |
| Coach "Why?" with a claim verifier and one repair attempt (needs `ANTHROPIC_API_KEY`; without it you get the checked facts) | MCP tools beyond `get_game`; a demo clip |

## Proof, not claims

- **Detector scores** on a frozen set: [`evals/reports/real_play_v1_2026-10-06.md`](evals/reports/real_play_v1_2026-10-06.md). Read its notes first: the set is curated puzzles plus hand-built positions, so the numbers show detection accuracy, not how often anyone makes these mistakes.
- **Explanation correctness (E2)**, 50 frozen positions from public Lichess puzzles: [`evals/reports/e2_v2_2026-10-09.md`](evals/reports/e2_v2_2026-10-09.md) and its [notes](evals/reports/e2_v2_2026-10-09_notes.md). Of the claims a program could check, 78% were correct with no evidence given to the model, 97% when it was given engine evidence, and **110 of 110 after the verifier** (95% interval 97% to 100%, so the 98% target is met as a point estimate but not established; 2 of the 50 verified texts could not be scored). The scorer is not independent of the verifier, many statements are still unverifiable (about 0.6 per text), no human reviewed the items or the extractions, and the raw baseline is the same model, not a GPT model ([design and limits](docs/decisions/0003-e2-eval-design.md), [what changed after the first run](docs/decisions/0004-e2-v2-changes.md)). The first run, on which the verifier scored 93%, is [here](evals/reports/e2_v1_2026-10-07.md).
- **Rules and state (E1)**: a randomized suite checks every action of 300 random game sequences against an independent python-chess reference ([`backend/tests/test_e1_rules_state.py`](backend/tests/test_e1_rules_state.py)). Zero violations. Cross-user access is not tested yet because there are no users.
- **Case study**: the 100-game baseline of my own Chess.com games is frozen with fingerprints ([ADR 0002](docs/decisions/0002-baseline-window.md)); the personal results stay out of this public repository. A 90-day write-up is still to come.

## Setup

```bash
cp .env.example .env     # fill in paths and keys; .env is git-ignored. Never put a key in .env.example
cd backend && uv sync && uv run pytest
uv run uvicorn app.api.main:app --port 8000   # restart after code changes (no auto-reload)
cd ../web && pnpm install && pnpm dev
```

Needs Stockfish (`STOCKFISH_PATH`). The coach needs `ANTHROPIC_API_KEY` in `.env`; model spend is logged locally and calls stop at `MONTHLY_BUDGET_USD` (default 10, an estimate from list prices; also set a spending limit in the Anthropic Console); without it everything else works and the
Why? and Review comparison show checked facts only. Docker/Postgres is not needed yet.

## Docs

- Where the project stands and what to do next: [`HANDOFF.md`](HANDOFF.md) and [`TASKS.md`](TASKS.md)
- How to review a pull request: [`REVIEW.md`](REVIEW.md)
- Product spec: [`docs/spec.md`](docs/spec.md)
- Agent instructions: [`AGENTS.md`](AGENTS.md)
- Decisions: [`docs/decisions/`](docs/decisions/)

## Licence

Copyright 2026 Karthik Raman. Licensed under the **GNU Affero General Public License v3.0 or later** (`AGPL-3.0-or-later`); see
[`LICENSE`](LICENSE). In short: you may use, study, modify and share this code, and if you run a modified version as a service
for other people you must offer them its source. The backend uses python-chess (GPL-3.0-or-later), which is why the project is
copyleft. Third-party components and their licences: [`THIRD_PARTY.md`](THIRD_PARTY.md).

Outside contributions are not being accepted yet. If that changes, contributors will be asked to sign a contributor
agreement first, so the project keeps the freedom to relicense or dual-license its own code.
