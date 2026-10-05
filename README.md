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

## Proof, not claims

- Eval reports comparing raw LLM vs grounded vs grounded + verified coaching → `evals/reports/`
- Detector precision/recall per tactic → `evals/reports/`
- A 90-day personal case study (Chess.com rapid 10|0 and 15|10) → coming

## Setup

```bash
cp .env.example .env     # fill in keys and paths
docker compose up -d db
cd backend && uv sync && uv run pytest
cd ../web && pnpm install && pnpm dev
```

## Docs

- Product spec: [`docs/spec.md`](docs/spec.md)
- Agent instructions: [`AGENTS.md`](AGENTS.md)
- Decisions: [`docs/decisions/`](docs/decisions/)
