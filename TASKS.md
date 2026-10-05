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
- [ ] T13 Precision/recall script on a FRESH, FROZEN set → first numbers in `evals/reports/`
  - Positions from real play, not self-play: Lichess puzzles tagged `hangingPiece` (rating 400–1200) and positions from Lichess rapid games rated 600–1000 (database.lichess.org, CC0). The puzzle file is downloaded (293 MB, `data/lichess/`, git-ignored). A month of standard rated games is about 28 GB compressed: never download it whole; stream it and stop early, keeping only rapid games with both players rated 600–1000, and ask before downloading
  - Adversarial cases on purpose: pinned capturers, pinned defenders, losing captures, several capturers on one target
  - Label rule written and frozen BEFORE running the detectors; ~30 labels hand-checked by me, recorded in the set README
  - Report each detector's version next to its numbers
  - **Status:** rule written and decided (`evals/sets/real_play_v1/LABEL_RULE.md`); set built as a DRAFT (202 items, `build_real_play_set.py`); hand-check sheets generated. Still to do: hand-check, freeze, run detectors, write the precision/recall script and report

## Day 5 — Blind-spot map + baseline
- [ ] T14 Run detectors over last 100 case-study games
  - `hanging_own`: report misses **per 100 moves** (its opportunity definition matches almost every position, so missed/available is not meaningful)
  - `missed_free`: report missed/available and rate per 100 moves
- [ ] T14b Peer benchmark: run the same detector versions over one month of Lichess rapid games rated 600–1200; store miss rates by rating band
  - Lichess and Chess.com ratings are on different scales: match bands by percentile or label the comparison "approximate"
  - Only the derived rates go in the repo; raw game files stay in `data/`
- [ ] T15 **Freeze baseline** in `data/baseline/` (hash recorded in `HANDOFF.md`)
- [ ] T16 Blind-spot map page

## Day 6 — Coaching
- [ ] T17 Coach agent harness: intent → tools → draft → verify → respond (one repair attempt)
- [ ] T18 Verifier: legality, line consistency, claim checks against engine/detectors
- [ ] T19 "What were you considering?" on review moments

## Day 7 — Evals + write-up
- [ ] T20 Freeze E2 set (~50 positions); run raw LLM vs grounded vs grounded + verifier
- [ ] T21 E1 state/rules regression suite
- [ ] T22 README update + short demo clip

## Housekeeping (any day)
- [ ] T23 GitHub Actions CI: install Stockfish, run `uv run pytest` (no engine skips), `ruff check`, and `pnpm exec tsc -b`
- [ ] T24 Choose and add a LICENSE. The backend depends on python-chess (GPL-3.0-or-later), so the repo should be GPL-3.0-or-later or AGPL-3.0-or-later (AGPL also covers people using a hosted version); MIT is not a safe choice for the combined work. Lichess GPL components (chessground, chessops, berserk) are not used. Decision pending (owner)

## Week 2 additions
- [ ] T25 Practice bank from the Lichess puzzle database (CC0), filtered by theme and rating, mixed with positions from my own games
- [ ] T26 Blind-spot map shows my rate next to the peer band from T14b
