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
- [ ] T13 Precision/recall script → first numbers in `evals/reports/`

## Day 5 — Blind-spot map + baseline
- [ ] T14 Run detectors over last 100 case-study games; missed/available + rate per 100 moves
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
