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
  - **Status:** set `real_play_v1` **frozen 2026-10-06** (rule v0.4; owner and GPT hand-checks done, see `evals/sets/real_play_v1/FROZEN.md`). Scored on 2026-10-06: report in `evals/reports/real_play_v1_2026-10-06.md` (detector versions, denominators, 95% Wilson intervals). Left for v2: the Lichess rapid-games sample (ADR 0001 A3; download needs approval, overlaps T14b)

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
- [x] T16 (v1: baseline results, two columns; trend and examples come later) Blind-spot map page: show 10|0 and 15|10 separately (ADR 0002)

## Day 6 — Coaching
- [x] T34 **Threat warning (Practice):** on your turn, "Watch out" lists pieces of yours the opponent can win by a legal capture (the `hanging_own` v2 definition), mate threats (the opponent would have a checkmate if you passed) and check; threatened squares are shaded red. Facts only (rules and detector, no engine, no LLM). `GET /games/{id}/threats`, `learner/threats.py`
- [x] T33 **Practice feedback (moved up by the owner, 2026-10-07):** after each move in Practice, a plain-words verdict (good / small slip / mistake / blunder) from the engine's evaluation drop, what was right or wrong from the detectors and mate scores, and the better move on request. No LLM. `GET /games/{id}/feedback/{ply}` (Practice only, 403 in Play), `learner/feedback.py`. Next: explain *why* with a verified line (T17/T18), threat warnings, fork detector
- [x] T17 (v1: one intent, `why_move`; see HANDOFF) Coach agent harness (one coaching focus per time control for now, ADR 0002): intent → tools → draft → verify → respond (one repair attempt)
- [x] T18 (v1; claim types in `coach/verifier.py`) Verifier: legality, line consistency, claim checks against engine/detectors
- [x] T19 (v1: facts + gaps; Review tab) "What were you considering?" on review moments

## Day 7 — Evals + write-up
- [x] T20 (first run 2026-10-07: `verified` 93% of checkable claims correct, target 98% NOT met as measured; see `evals/reports/e2_v1_2026-10-07.md` and `_notes.md`) Freeze E2 set (~50 positions); run raw LLM vs grounded vs grounded + verifier
- [x] T21 (2026-10-08; cross-user access is a visible skip until sign-in exists) E1 state/rules regression suite: `backend/tests/test_e1_rules_state.py`
- [~] T22 README update done 2026-10-08; the demo clip is still to be recorded by the owner (screen recording of play, Practice feedback, Review and Blind spots; keep real game data and opponent names out of the clip or blur them)

## Housekeeping (any day)
- [x] T42 Move badges (owner, 2026-10-09: "a star on the piece ... book move, star move, thumbs up, ? mark, wrong move"): after each Practice move a badge sits on the square it was played to and in the verdict line: 📖 book, ★ best, 👍 good, ?! inaccuracy, ? mistake, ?? blunder. Book comes from a starter list of about 60 opening lines (`core/openings.py`), not a full database. Not done: Brilliant and Great (need sacrifice and only-move detection)
- [ ] T43 Full opening book: replace the starter list with the CC0 lichess-org/chess-openings tables (needs the owner's OK to download about 0.5 MB, and a THIRD_PARTY.md row)
- [x] T41 Hint on the main board (owner, 2026-10-09: "show the stronger move on the board itself on hint"): the 💡 switches the main board to the position before the player's last move with the green arrow drawn on it (the only position the suggestion is valid for), a yellow banner says so, moves are disabled while it shows; "Back to my game" or Esc returns to the live game. The small separate hint board is gone
- [x] T40 Practice keyboard and board marks (owner, 2026-10-09): the left arrow key is Undo (Practice only; not while typing or in a menu); after a suboptimal move the board itself marks your piece that can be taken (red, kept on the square where it was taken) and a free piece you could have taken (green, while it is still there); `marks` in the feedback response, engine-confirmed misses only. **Open question for the owner:** by "good moves" did they also want the best-move arrow shown automatically on the board? (Today it stays behind the 💡, as they asked earlier.)
- [x] T38 Practice UI (owner's first requests, 2026-10-09): a vertical evaluation bar beside the board (Practice only; `GET /games/{id}/eval`) replaces the "cost in pawns" sentence; the better move is a green arrow on the board instead of words, **never shown unless the player clicks the 💡 hint icon** (owner: don't be proactive), a suggestion that can be toggled off, drawn on a small board of the position before the move (review fix 2026-10-09)

- [x] T39 Unlimited Undo in Practice (owner, 2026-10-09: "let the user undo any number of moves"): the two-in-a-row cap is removed; Undo works back to the start of the game; the API field `takebacks_left` is replaced by `can_take_back`; error code `takeback_limit` is gone
- [ ] T37 E2 follow-ups from the v2 notes: claim types `gives_check` and forced-reply, let the extractor express harness-provided facts, a person reads 15-20 extractions, a GPT raw baseline; any change is a new version and a run on a new set
- [x] T36 Model spend ledger and monthly budget guard (2026-10-09): every API call recorded in `data/usage/` with tokens and estimated dollars; calls stop at `MONTHLY_BUDGET_USD` (default 10); `GET /usage`; a spend line in the app; eval runs print the month's spend and refuse to start if the budget cannot cover them
- [ ] T23 GitHub Actions CI: install Stockfish, run `uv run pytest` (no engine skips), `ruff check`, and `pnpm exec tsc -b`
- [x] T24 Licence chosen and added: **AGPL-3.0-or-later** (decided 2026-10-07 because python-chess is GPL-3.0-or-later; AGPL also covers hosted use). `LICENSE`, `THIRD_PARTY.md`, licence fields in `pyproject.toml` and `package.json`, README section. Rule: every new dependency gets a `THIRD_PARTY.md` row first (a test enforces it and fails on any new copyleft package)
  - Follow-ups: if outside contributions are ever accepted, add a contributor agreement first; before publishing a built web bundle, include the bundled packages' licence notices

- [ ] T30 Persist games in Postgres (they are in memory today and vanish on restart); needs Docker installed and a database-level guard instead of the in-process lock
- [x] T35 (2026-10-09: verifier v2, `why_v2`, `extract_v2`, frozen `e2_v2`, final run: `verified` 110/110, target met as a point estimate; see `evals/reports/e2_v2_2026-10-09_notes.md`; still open as T37: a person reading a sample of extractions, a GPT raw baseline, more claim types) E2 follow-ups from the notes: sequence check in the verifier (v2), `extract_v2` that never infers bands, a person reads a sample of extractions, decide on unverifiable statements (`why_v2`), a GPT raw baseline; then E2 v2 run
- [ ] T31 Flag fast-pass evaluations as uncertain when unstable (spec B2): compare a second depth
- [ ] T32 Cache reviews (each call re-runs the deep check)

## Next (proposed order for the next session)
1. **T44 Training sessions** (the stepped hint ladder part is built, see T46; sessions and the practice bank remain)
   Original scope: **T44 Training sessions and the hint ladder** (spec D3 to D5): five positions per session (two from the owner's games, two curated on the same motif, one held-out test), stage 0 scan prompt, concept cue, piece or square, consequence, answer on request; fading scan prompts. Needs T25 (practice bank). No API spend. Assisted results labelled as such
2. **Owner's open questions** (ADR 0005): arrow after a suboptimal move, +0.3 start evaluation, opening list download (T43)
3. **T37** E2 follow-ups; **T45** MCP tools usable from a chat (a board image works in any client; an interactive board only where the client supports MCP interactive UI): spec Week 3
4. **T23** CI with Stockfish, **T30** Postgres persistence, the demo clip (owner)

## Week 2 additions
- [ ] T25 Practice bank from the Lichess puzzle database (CC0), filtered by theme and rating, mixed with positions from my own games
  - ADR 0001 §3: theme matches the user's active pattern, rating within ±200 of the user's level; mix per session: 2 from own games, 2 curated Lichess puzzles, 1 held-out test (spec D3), and held-out items never appear in practice or coaching context; store puzzle IDs and the dataset snapshot date, not copies of the CSV
- [ ] T26 Blind-spot map shows my rate next to the peer band from T14b

## Later (from ADR 0001, `docs/decisions/0001-open-source-reuse.md`)
- [ ] T27 (Month 2) Miss-likelihood model: P(a player at rating R misses a free piece / hangs a piece) in a given position. Data: Lichess games (labels from our detectors) and ChessBench (Stockfish values; code Apache-2.0, data CC0 + CC-BY 4.0, attribute CC-BY); Maia-2 (MIT) as features or baseline. Read the Maia group's published work first and state what is new; evaluate on a held-out month and report calibration, not just accuracy
- [ ] T28 (V1.1) Maia-2 opponent at the user's rating band, with Stockfish skill levels as the fallback; label strength by Maia band, not as an Elo claim. First check its lowest supported rating band against users under 1000 (spec A2); record the model and weights version
- [ ] T29 (optional; the licence is now decided) Board and client upgrades: chessground (GPL-3.0) for arrows and mobile, chessops for client-side hints (the backend stays authoritative), stockfish-web for in-browser analysis. Not needed now

- **T46 (done 2026-10-10): stepped hint ladder in Practice.** `GET /games/{id}/hint?level=1..5` (scan prompt, kind of move, which piece, what it does, the move; spec D4); `backend/app/learner/hints.py`; hints counted per position (`hints_used` in the game view). Next: store hints per game permanently for the progress page, and fade the scan prompt.
