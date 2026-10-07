# TASKS.md — Week 1 (paste into GitHub Issues if preferred)

Each task should fit one 1–2 hour session. Tick when merged to `main`.

## Day 1 — Foundations
- [x] T01 Repo skeleton per `AGENTS.md` layout; `docker-compose.yml` with Postgres
- [x] T02 `core/`: create game, legal move, illegal move rejected, outcomes (mate, stalemate, draws), PGN export — with tests
- [x] T03 Web: board renders, sends move to API, shows server-confirmed position
- [x] T04 MCP skeleton exposing `get_game`

## Day 2 — Play
- [x] T05 Engine wrapper (version + budget recorded; scores normalised to player's side; mate handled separately)
- [x] T06 Play vs Stockfish: level, colour, resign, game end
- [x] T07 Play/Practice flag; `assisted` set permanently on switch

## Day 3 — Sync + analysis
- [x] T08 Chess.com sync: serial requests, User-Agent, filter 10|0 and 15|10, dedupe by game URL
- [x] T09 Count available case-study games → note in `HANDOFF.md`
- [x] T10 Batch shallow engine pass over synced games; review of one game (up to 3 key moments)

## Day 4 — Detectors
- [x] T11 `hanging_own` v1 detector + 50 labelled positions in `evals/sets/hanging_own_v1/`
- [x] T12 `missed_free` v1 detector + 50 labelled positions
- [x] T13 Precision/recall script on a FRESH, FROZEN set → first numbers in `evals/reports/` (done 2026-10-06: `evals/reports/real_play_v1_2026-10-06.md`)
  - Positions from real play, not self-play: Lichess puzzles tagged `hangingPiece` (rating 400–1200) and positions from Lichess rapid games rated 600–1000 (database.lichess.org, CC0). The puzzle file is downloaded (293 MB, `data/lichess/`, git-ignored). A month of standard rated games is about 28 GB compressed: never download it whole; stream it and stop early, keeping only rapid games with both players rated 600–1000, and ask before downloading
  - Adversarial cases on purpose: pinned capturers, pinned defenders, losing captures, several capturers on one target
  - Label rule written and frozen BEFORE running the detectors; ~30 labels hand-checked by me, recorded in the set README
  - Report each detector's version next to its numbers
  - Follow `docs/decisions/0001-open-source-reuse.md` §3. Puzzle format: `FEN` is the position **before** the opponent's move and `Moves[0]` is that move (a real blunder), so `hanging_own` uses `(FEN, Moves[0])` and `missed_free` uses the position after `Moves[0]` (ADR amendments A1, A2). The games sample is deferred to v2 (A3)
  - **Status:** set `real_play_v1` **frozen 2026-10-06** (rule v0.4; owner and GPT hand-checks done, see `evals/sets/real_play_v1/FROZEN.md`). Still to do: the precision/recall script and report (run both detectors, publish numbers with versions, denominators, intervals)

## Day 5 — Blind-spot map + baseline
- [x] T14a Choose and **record the baseline window** (done 2026-10-07: frozen, see `docs/decisions/0002-baseline-window.md`; the 10|0 and 15|10 games are kept as two separate 50-game lists): the last 100 Chess.com rapid games (10|0 and 15|10) before training starts; game ids in `data/baseline/` (git-ignored), hash in `HANDOFF.md`; report the mix per time control. Propose to the owner first. Freeze before any coaching on these games (see T15)
- [x] T14 (code done and run 2026-10-07; results in `data/patterns/`, not frozen) Run detectors over the baseline window (new `backend/app/learner/` pattern layer, with tests)
  - Evidence comes from the stored fast pass (`data/analysis/`, schema 2, depth 10); uncertain results are excluded from numerator and denominator and reported separately
  - Report **per time control only** for now (owner decision 2026-10-07, ADR 0002; the pooled figure is deferred, not dropped), with detector versions, denominators, intervals and the tentative/established labels (spec C3)
  - Expect misses in already-lopsided positions to show as `uncertain` (T13 finding)
  - `hanging_own`: report misses **per 100 moves** (its opportunity definition matches almost every position, so missed/available is not meaningful)
  - `missed_free`: report missed/available and rate per 100 moves
- [ ] T14b Peer benchmark: run the same detector versions over one month of Lichess rapid games rated 600–1200; store miss rates by rating band
  - Lichess and Chess.com ratings are on different scales: match bands by percentile or label the comparison "approximate"
  - Only the derived rates go in the repo; raw game files stay in `data/`
  - ADR 0001 §3: one month, both players rated 600–1200 in bands of 100; same detector versions as the baseline; store aggregates (per band: missed, available, moves, games) in `evals/benchmarks/peer_<yyyy-mm>_<detector>_v<N>.json`; stream-decompress zstd, never load a month into memory; **never show a peer comparison without the rating-scale note**; ask before downloading (a month is about 28 GB)
- [x] T15 (done 2026-10-07, sha256 in `HANDOFF.md`) Freeze the baseline **results** in `data/baseline/` once T14 has produced them (hash recorded in `HANDOFF.md`). The window itself is already frozen (T14a)
- [ ] T16 Blind-spot map page: show 10|0 and 15|10 separately (ADR 0002)

## Day 6 — Coaching
- [ ] T17 Coach agent harness (one coaching focus per time control for now, ADR 0002): intent → tools → draft → verify → respond (one repair attempt)
- [ ] T18 Verifier: legality, line consistency, claim checks against engine/detectors
- [ ] T19 "What were you considering?" on review moments

## Day 7 — Evals + write-up
- [ ] T20 Freeze E2 set (~50 positions); run raw LLM vs grounded vs grounded + verifier
- [ ] T21 E1 state/rules regression suite
- [ ] T22 README update + short demo clip

## Housekeeping (any day)
- [ ] T23 GitHub Actions CI: install Stockfish, run `uv run pytest` (no engine skips), `ruff check`, and `pnpm exec tsc -b`
- [x] T24 Licence chosen and added: **AGPL-3.0-or-later** (decided 2026-10-07 because python-chess is GPL-3.0-or-later; AGPL also covers hosted use). `LICENSE`, `THIRD_PARTY.md`, licence fields in `pyproject.toml` and `package.json`, README section. Rule: every new dependency gets a `THIRD_PARTY.md` row first (a test enforces it and fails on any new copyleft package)
  - Follow-ups: if outside contributions are ever accepted, add a contributor agreement first; before publishing a built web bundle, include the bundled packages' licence notices

- [ ] T30 Persist games in Postgres (they are in memory today and vanish on restart); needs Docker installed and a database-level guard instead of the in-process lock
- [ ] T31 Flag fast-pass evaluations as uncertain when unstable (spec B2): compare a second depth
- [ ] T32 Cache reviews (each call re-runs the deep check)

## Week 2 additions
- [ ] T25 Practice bank from the Lichess puzzle database (CC0), filtered by theme and rating, mixed with positions from my own games
  - ADR 0001 §3: theme matches the user's active pattern, rating within ±200 of the user's level; mix per session: 2 from own games, 2 curated Lichess puzzles, 1 held-out test (spec D3), and held-out items never appear in practice or coaching context; store puzzle IDs and the dataset snapshot date, not copies of the CSV
- [ ] T26 Blind-spot map shows my rate next to the peer band from T14b

## Later (from ADR 0001, `docs/decisions/0001-open-source-reuse.md`)
- [ ] T27 (Month 2) Miss-likelihood model: P(a player at rating R misses a free piece / hangs a piece) in a given position. Data: Lichess games (labels from our detectors) and ChessBench (Stockfish values; code Apache-2.0, data CC0 + CC-BY 4.0, attribute CC-BY); Maia-2 (MIT) as features or baseline. Read the Maia group's published work first and state what is new; evaluate on a held-out month and report calibration, not just accuracy
- [ ] T28 (V1.1) Maia-2 opponent at the user's rating band, with Stockfish skill levels as the fallback; label strength by Maia band, not as an Elo claim. First check its lowest supported rating band against users under 1000 (spec A2); record the model and weights version
- [ ] T29 (optional; the licence is now decided) Board and client upgrades: chessground (GPL-3.0) for arrows and mobile, chessops for client-side hints (the backend stays authoritative), stockfish-web for in-browser analysis. Not needed now
