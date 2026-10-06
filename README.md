# AI Chess Coach

> Work in progress — built in public.

A chess coach that plays, analyses, finds your recurring tactical misses, and coaches you with explanations that are **checked against the engine before you see them**. Progress is measured in your real games, not just puzzles.

## Why

Players under ~1200 lose most games to the same misses — hanging pieces and missed threats. Engine reviews flag the move but not the pattern, AI explanations are sometimes confidently wrong, and nothing shows whether training changed anything.

## What it does

- **Play** against Stockfish (Maia-2 human-like opponent planned)
- **Analyse** games played here, synced from Chess.com/Lichess, or imported as PGN
- **Find patterns** as rates — e.g. "missed 6 of 9 free pieces"
- **Coach** with verified explanations, a hint ladder, and practice from your own positions
- **Measure** miss rates in real games against a frozen baseline

## Where it is today

| Works | Not yet |
|---|---|
| Play vs Stockfish in the web app (click to move, Level 1-10, resign, PGN download) | Blind-spot map page |
| Practice mode with Undo, always marked "assisted" | Coach explanations and the verifier |
| Chess.com sync, batch engine analysis, post-game review (up to 3 verified moments) | Training sessions, Lichess sync, Maia-2 opponent |
| Two detectors: `hanging_own` and `missed_free` (versioned) | Detectors over your own games (next: T14) |
| A frozen real-play eval set and the first detector scores | Postgres persistence, sign-in |

## Proof, not claims

- Detector scores on a frozen set: [`evals/reports/real_play_v1_2026-10-06.md`](evals/reports/real_play_v1_2026-10-06.md). Read its notes before quoting a figure: the set is curated puzzles plus hand-built positions, so the numbers show detection accuracy, not how often anyone makes these mistakes.
- Eval reports comparing raw LLM vs grounded vs grounded + verified coaching → `evals/reports/` (coming)
- A 90-day personal case study (Chess.com rapid 10|0 and 15|10) → coming

## Setup

```bash
cp .env.example .env     # fill in keys and paths
docker compose up -d db
cd backend && uv sync && uv run pytest
cd ../web && pnpm install && pnpm dev
```

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
