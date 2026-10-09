# HANDOFF.md

Update this at the end of every session (any agent, any machine). Newest entry on top of the Log. Keep each entry short.

---

## Start here (new session)

1. `cd ~/Projects/ai-chess-generator-coach`. Read `AGENTS.md`, this file, then `REVIEW.md`. Spec: `docs/spec.md` (v0.4). Open decisions: `docs/decisions/0001-open-source-reuse.md`.
2. **No feature PRs are open** (T14-T19, T33, T34 and the review fixes are merged). Work from `main`: `git checkout main && git pull`.
3. Check the machine: `cd backend && uv sync && uv run pytest -q && uv run ruff check .` should pass with clean lint (**278 passed** on 2026-10-07; the count grows as tests are added). `cd ../web && pnpm install && pnpm test && pnpm exec tsc -b`.
4. Take the next task from "Next up" below, on a branch `feat/<name>` or `fix/<name>`, one task per PR.

## Current state

- **Phase:** Week 1 is built through Day 6: detectors, baseline (frozen, with results), blind-spot map, Practice feedback, threat warnings, verifier, coach harness (`why_move`), "What were you considering?". **Not yet:** Day 7 evals (T20 E2 raw vs grounded vs verified, T21 E1 rules suite), README and demo (T22), training sessions and hint ladder, MCP tools beyond `get_game`. First usable version due 12 Oct 2026.
- **Branches:** everything is on `main`.
- **Coach:** needs `ANTHROPIC_API_KEY` in the git-ignored repo-root `.env` (never in `.env.example`; a key was once committed there by mistake on 2026-10-07 and had to be revoked; the history still holds the revoked key). Without a key the Why? button and the Review comparison fall back to checked facts. Model: `COACH_MODEL` (default `claude-sonnet-5-5`). Turn on GitHub secret scanning and push protection for the repo if it is not already on.
- **Detector versions (report them with any number):** `hanging_own` v2, `missed_free` v2 (both use legal captures and legal recaptures). Analysis record schema: 2 (`engine/batch.py`). Engine: Stockfish 19.
- **Baseline window frozen?** **Yes (2026-10-07)**: the 100 most recent case-study games, as two lists (50 at 10|0, 50 at 15|10). sha256: whole `87217baf...aa7b`, 10|0 `7ac385a0...c4c2`, 15|10 `01b8d1cb...1aad` (full values in `docs/decisions/0002-baseline-window.md`). Ids live only in `data/baseline/baseline_window_v1.json` (git-ignored, read-only). **Baseline results frozen (T15, 2026-10-07):** `data/baseline/baseline_results_v1.json`, read-only, sha256 `bbbd9babac37731925005d5ffbed7d8f2e88feee35972a5f1f58261c60952c3e` (detectors `hanging_own` v2 and `missed_free` v2, Stockfish 19 depth 10). Check with `sha256sum`. The coach may now be used on these 100 games. Do not use the coach on these 100 games until the results are frozen (T15).
- **Frozen eval sets:** `evals/sets/real_play_v1` (frozen 2026-10-06; full hashes in its `FROZEN.md`; a test fails if they change). The older `hanging_own_v1` and `missed_free_v1` are superseded drafts (easy, engine-labelled, unreviewed): do not score or quote them.
- **First scores:** `evals/reports/real_play_v1_2026-10-06.md` (+ `.json`, `_notes.md`). Read the notes before quoting anything.
- **What exists:** play vs Stockfish in the web app (click to move, Level 1-10, resign, PGN, Play/Practice with Undo, 1 s reply pause); FastAPI + shared tool layer; MCP `get_game` skeleton; Chess.com sync; batch fast pass + post-game review (`GET /synced-games/{id}/review`); detectors `hanging_own` and `missed_free`; eval tooling (`evals/tools/`).
- **What does not exist yet:** the pattern layer that applies the detectors to real games (T14), blind-spot map page (T16), coach agent and verifier (T17-T19), training sessions, Postgres persistence (games live in memory and vanish on restart), sign-in, Lichess sync, Maia-2.
- **Machine facts (this MacBook):** repo at `~/Projects/ai-chess-generator-coach`. Installed via Homebrew: `uv`, `pnpm`, `stockfish` (`/opt/homebrew/bin/stockfish`). **Docker is not installed.** `.env` (git-ignored) holds the Chess.com username (`karry261990`), the contact email for the User-Agent, `STOCKFISH_PATH`, case-study time controls `600,900+10`.
- **Local data (git-ignored, never commit):** `data/games/chesscom_karry261990.jsonl` (450 case-study games: 253 at 10|0, 197 at 15|10, 4 Jul to 5 Oct 2026); `data/analysis/chesscom_karry261990.jsonl` (fast pass for all 450, schema 2, depth 10); `data/lichess/lichess_db_puzzle.csv.zst` (293 MB, CC0). No Lichess games file has been downloaded (one month is about 28 GB; stream and cut off; ask first).
- **Run the app:** `cd backend && uv run uvicorn app.api.main:app --port 8000` (no `--reload`, restart after code changes) and `cd web && pnpm dev`.

## Next up

**T14a. Baseline window: DONE** (frozen 2026-10-07, ADR 0002). Verify with `cd backend && uv run python -m app.learner.baseline verify`.

**T14. The pattern layer: DONE** (`backend/app/learner/patterns.py`, 10 tests; run `cd backend && uv run python -m app.learner.patterns baseline`; output `data/patterns/baseline_patterns_v1.json`, git-ignored, not frozen). Original spec kept below for reference. For each user move in each game: board before the move, the move, `Evidence(best_cp, after_cp)` built from the stored fast-pass positions (White's view; use `learner.review.rank_for_mover` for the mover's side), then `detectors.hanging_own.detect` and `detectors.missed_free.detect`. Record opportunity -> taken / missed / uncertain / not_applicable per move. Metrics:
- `hanging_own`: misses **per 100 moves** (its opportunity held in about 81% of 445 weak-engine self-play positions, so missed/available is not meaningful; re-measure on real games)
- `missed_free`: missed / available, and per 100 moves
- uncertain results are excluded from numerator and denominator (AGENTS rule 5) and reported separately
- **per time control only** (owner decision 2026-10-07: keep 10|0 and 15|10 separate for now; no pooled figure; ADR 0002); show sample sizes; label tentative (at least 3 misses across at least 2 games) versus established (at least 8 opportunities) per spec C3; report detector versions, denominators and intervals
- **Expect** misses made in already-lopsided positions to appear as `uncertain` (T13 finding: the engine under-reports a hung piece when a position is already won or lost)

Then T16 (blind-spot map page). Later: T14b peer benchmark (needs Lichess games; ask before downloading), T23 CI with Stockfish, T30 Postgres persistence, T31 fast-pass uncertainty flag. Details in `TASKS.md`.

## Decisions waiting on the owner

- Whether to download a Lichess games sample for T14b (ask first; about 28 GB a month).

## Working agreement with the owner (observed; follow it)

- **Decisions:** the owner delegated chess and eval decisions ("you decide, keep it reversible"). Decide, write the reason and how to reverse it in the repo, and say so plainly.
- **Merging:** the owner says "merge" explicitly each time. Open PRs, wait, merge in order. Deleting the base branch of a stacked PR auto-closes the stacked PR (happened to #10): rebase it onto `main` and open a new PR instead. Check `git branch --show-current` before committing; two commits once landed on the wrong branch.
- **Communication:** the owner is rated under 1000 and finds chess notation and abstract wording hard. Use plain words, short steps, concrete examples, no jargon. For anything the owner must judge, give a visual page with Yes / No / Can't tell (the hand-check page is the model).
- **Honesty:** never quote the eval numbers as real-play performance; state what a number does not show; report failures and your own mistakes openly; do not move goalposts after seeing results (if a step is added late, say so in the record).
- **Reviews:** GPT reviews PRs following `REVIEW.md` and leaves inline comments. Reproduce each finding first, fix it, reply in the thread, then resolve the thread. Update the PR's "Reviewed by" section.
- **Privacy:** the repo is public. Nothing from `.env`, `data/`, the owner's games, or the contact email goes into a commit.

## Blockers / open questions

- Fast-pass evaluations are not flagged uncertain when unstable (spec B2); needs a second-depth comparison.
- Reviews are not cached; each call re-runs the deep check (a few seconds).
- Games are held in memory only; the per-game lock is in-process only (several workers would need a database guard). Docker/Postgres are not set up.
- Web has unit tests for the response-ordering rule but no component or browser tests.
- Draws end only when reached; players cannot claim a draw yet.
- `real_play_v1` labels have had limited review (82 of 202 items; a checker under 1000 and GPT; no strong human player). `missed_free` has no real missed examples in it, so its recall on real ignored free pieces is unmeasured.

---

## Log

### 2026-10-09 · MacBook · Claude Code (session 24, part 4)
- **Unlimited Undo (T39), owner's request.** The earlier rule "at most 2 undos in a row" (session 8, see that entry) is **reversed**: Undo in Practice works as many times as the player likes, back to the start (the engine's reply goes with the player's move; takebacks still never happen in Play or after resigning, and still mark the game assisted for good). `Game.takebacks_in_row` and `MAX_TAKEBACKS` are gone; the view field `takebacks_left` is now `can_take_back` (bool); the page shows a plain "Undo" button. Tests updated (core, API, and the E1 suite: invariant I5 now says no cap and checks `can_take_back` against the reference). 629 backend and 34 web tests.
- **Stacked on PR 47** (evaluation bar and hint arrow), because that branch's arrow caption also used the old field. Merge 47 first.
- **Test-run note:** several overlapping `uv run pytest` jobs queue behind uv's environment lock; a full run is about 40 seconds when started alone.
- **Branch / PR:** `feat/unlimited-undo`

### 2026-10-09 · MacBook · Claude Code (session 24, part 3)
- **First changes requested by the owner while practising (T38).** (1) **Evaluation bar:** a vertical bar beside the board in Practice, like chess sites: White's share from a logistic of the engine score (a mate fills the bar), a small label (+1.4, M3), words on hover, turns with the board for Black, refreshed after every move (mine and the opponent's). `GET /games/{id}/eval` (Practice only, 403 in Play, depth 12, White's side, returns the revision). The "this cost you about X pawns" sentence is gone. (2) **Arrow instead of words, only on request:** after the owner plays, a 💡 hint icon appears next to Why? (only when the move was not the best); the green arrow for the stronger move is drawn **only after the owner clicks it** ("don't be proactive"), is a suggestion only (any move may be played), toggles off, and shows a short note instead when the board has moved on so that its starting square no longer holds one of the player's pieces. The "Show the better move" button and the text are gone.
- **Tests:** 2 backend (one with Stockfish, including a mate score), 7 web (bar maths and words, arrow check). Checked in the browser.
- **Owner question, answered in chat:** Chess.com itself cannot be launched inside Claude or ChatGPT (its public API is read-only, its site is not embeddable); our own board could be put in a chat through MCP tools: a board image works in any client, an interactive board only where the client supports MCP interactive UI (check current docs). Spec Week 3; not started.
- **Branch / PR:** `feat/eval-bar-and-arrow`

### 2026-10-09 · MacBook · Claude Code (session 24, part 2)
- **E2 v2 final run done** on the frozen fresh set `e2_v2` (run once from scratch after the credit interruption; nothing changed in between). Claim correctness: raw 125/160 (78%), grounded first draft 119/123 (97%), **verified 110/110 (100%, 95% interval 97% to 100%)**; texts with a wrong claim 25, 4, 0 of 50; 12 of 50 drafts repaired, none fell back; 3 texts unscored (extraction failed twice; 2 of them `verified`); unverifiable statements 238, 33, 30. Cost 2.05 dollars. `evals/reports/e2_v2_2026-10-09.md` and `_notes.md` (read the notes first).
- **Reading it honestly:** the 98% target is met as a point estimate, not established (lower bound 97%); the scorer is not independent of the verifier; many statements remain unverifiable (examples: "gives check", "forces White to respond"; also facts the detector gave the harness but the extractor cannot express); no human has reviewed the items or the extractions. Evidence cuts wrong texts from 25 to 4 of 50 and the verifier removed the other 4.
- **State of PRs:** 43 and 45 (T35 and the budget guard) merged, no PRs open except `docs/e2-v2-result` (this note, README and TASKS). This month's recorded model spend is 8.85 of 10 dollars (includes the 6.80 estimate row); raise `MONTHLY_BUDGET_USD` before more paid runs.
- **Next:** training sessions and the hint ladder (spec D3/D4/D5), MCP tools, T37 (E2 follow-ups), the demo clip (owner). First usable version date was 12 Oct.
- **Branch / PR:** `docs/e2-v2-result`

### 2026-10-09 · MacBook · Claude Code (session 24)
- **T36 done: usage ledger and budget guard** (owner asked after the credit ran out mid-eval, about 6.8 dollars of eval runs in two days). `backend/app/coach/usage.py`: every `AnthropicDrafter` call is recorded (model, tokens, estimated dollars, purpose) in `data/usage/usage_YYYY-MM.jsonl` (git-ignored); before each call the guard raises `CoachUnavailable` when the month's recorded spend has reached `MONTHLY_BUDGET_USD` (default 10), so the coach falls back to checked facts instead of failing; `GET /usage`; a spend line under the tabs (warns at 80%, says plainly at 100%); `run_e2.py` prints the month's spend and the run's estimated cost (about 0.04 dollars per position) and **refuses to start if the budget cannot cover it**. `.env.example` now has `MONTHLY_BUDGET_USD` (the unused INR line is gone). 29 new tests including a fake Anthropic client, month rollover, a corrupt ledger line, and the guard sending nothing.
- **Limits:** dollars are estimates from list prices (unknown models are priced as the most expensive one); the Console is the authority and a spending limit there is the real hard stop (the owner should set one); the check is made before a call so one call can overshoot by its own cost; the ledger knows only calls made through this code. **A local estimate row of 6.80 dollars ("backfill_estimate_before_ledger") was added to the owner's October ledger for spend before the ledger existed**; edit or delete that line in `data/usage/usage_2026-10.jsonl` if the Console shows a different figure.
- **Process note:** this branch was first cut from `main`, which lacked PR 43's runner changes, so two edits to `run_e2.py` silently did nothing until I noticed; it is now stacked on `feat/verifier-v2` (PR 43). Merge 43 first.
- **Still blocked:** the final `e2_v2` run needs Anthropic credit. With the ledger it will show what is left of the month's budget before it starts.
- **Branch / PR:** `feat/usage-budget-guard`, stacked on `feat/verifier-v2`

### 2026-10-08 · Cloud · Claude Code (session 23)
- **Docs only:** the T13 "Status" line in `TASKS.md` still said the precision/recall script and report were to do; both were done on 2026-10-06. It now points at the report and names what is left for v2 (the rapid-games sample, ADR 0001 A3). The old `feat/t13-build-real-play-set` branch is fully on `main`; nothing else remains for T13.
- **Branch / PR:** `docs/t13-status-note`

### 2026-10-08 · MacBook · Claude Code (session 22, part 3)
- **T35 mostly done; final run blocked.** Verifier **v2** (`check_sequences`: a sentence that names two or more moves as a line of play must match a verified `line_legal` claim or an engine line, in order and contiguous), coach prompt `why_v2` (now the default; `why_v1` stays frozen on disk), `extract_v2` (literal extraction), runner options (`run e2_v2`, `rescore`, `--resume`), ADR 0004. 616 backend tests.
- **Development run on the e2_v1 positions (tuning, NOT a result):** new stack `verified` 119/119 (100%), `grounded` 122/124, `raw` 118/163; unverifiable statements in `verified` 22 (was 68). Re-scoring the old v1 texts with `extract_v2` gave `verified` 131/138 (95%), so the stricter extractor alone moved 93% to 95%; the rest is the new prompt and verifier, measured on positions they were designed against.
- **Fresh frozen set `e2_v2`** (50 new Lichess puzzles, none from v1; hashes in its `FROZEN.md`, enforced by a test) built and frozen **before** the final run. **The final run started and then stopped at item 45 because the Anthropic account ran out of credit** ("credit balance is too low"). It lost its results: the runner wrote results only at the end. Fixed: finished items are now saved to `items.jsonl` as they complete and `--resume DIR` continues (a test covers an interruption). The runner changed after the freeze; scoring did not (recorded here; the runner hash in `FROZEN.md` is for the version at the freeze).
- **To finish T35:** top up Anthropic credit, then `cd backend && uv run python ../evals/tools/run_e2.py run e2_v2` (about 1.8 dollars, about 30 minutes; it prints a resume command if interrupted), then `uv run python ../evals/tools/report_e2.py ../evals/runs/e2_v2_<time>/results.json`, write notes next to the report, update README's E2 line. Target unchanged: 98% of checkable claims for `verified`; report the result whatever it is.
- **Also open:** a person reads a sample of extractions; a GPT raw baseline; unverifiable statements still many.
- **Branch / PR:** `feat/verifier-v2`

### 2026-10-08 · MacBook · Claude Code (session 22, part 2)
- **T22 README done; demo clip not done.** README now has the architecture sketch, an honest works / not-yet table, the E1 and E2 results with their caveats (E2: 80% raw, 93% grounded, 93% verified, target not met as measured), and setup notes (key in `.env` only). The owner's personal baseline numbers are deliberately not in it. **The clip is the owner's to record** (no screen recorder is available to the agent without capturing the whole desktop): show Play, Practice feedback and Why?, Review with the "What were you considering?" box, and Blind spots; real opponent names and results are on screen in the Review list and Blind spots numbers, so crop or blur them before sharing.
- **Branch / PR:** `docs/readme-t22`

### 2026-10-08 · MacBook · Claude Code (session 22)
- **T21 done: E1 rules and state suite** `backend/tests/test_e1_rules_state.py`. 300 seeded random action sequences on the game core (legal and illegal moves, garbage, stale and duplicate revisions, mode switches, takebacks, resignations, with and without an engine opponent) are checked after every action against an independent python-chess reference for invariants I1-I8 (docstring): accepted actions change state exactly as the reference says, rejected ones change nothing, the revision only goes up by 1 per accepted action, position and outcome match the reference, `assisted` never goes from true to false, takeback rules, a duplicate never applies twice, nothing is accepted after game over, and the PGN replays with the right Assisted/Mode headers. 20 more sequences over HTTP. A reach test fails if the sequences stop reaching takebacks, assisted Play games and resignations. **Result: zero violations.**
- **Does the suite catch bugs?** Six planted bugs in `core/game.py`: five were caught at once (no revision bump, switching to Play clears assisted, takeback limit removed, moves allowed after game over, stale revision ignored). One survived: "takeback forgets to mark assisted", which cannot be observed because takebacks exist only in Practice and a Practice game is already assisted (that line is defensive).
- **Not tested, on purpose:** cross-user access (E1 lists it) needs sign-in and game ownership (spec Week 4); it is a visible `skip` with that reason, not a silent pass.
- **Finding, not a bug:** a duplicate move over HTTP is refused with `not_your_turn`, not `revision_conflict`, because the turn check runs first; both refuse it.
- **Old API key:** the owner confirmed on 2026-10-07 that the key committed to `.env.example` was deleted. Item closed.
- **Next:** T22 (README, demo clip; first usable version due 12 Oct), then T35.
- **Branch / PR:** `feat/e1-rules-suite`

### 2026-10-07 · MacBook · Claude Code (session 21, part 9)
- **Test bug fixed:** `test_the_report_states_scoring_coverage` wrote its test report to the same date-named file as the real E2 report and then deleted it, so running the tests removed `evals/reports/e2_v1_2026-10-07.md` from the working tree (GitHub's copy was never affected; restored with `git checkout`). The test now uses a 1999 date, so it can never touch a real report.
- **End of day state:** `main` is at the merge of PR 39; no other PRs open except the one for this fix (`fix/report-test-clobber`). Backend 287 tests, web 24. Open: T35 (E2 follow-ups), T21 (E1 rules suite), T22 (README and demo clip, first usable version due 12 Oct), training sessions and hint ladder, T14b (Lichess sample, ask first).

### 2026-10-07 · MacBook · Claude Code (session 21, part 8)
- **T20 done: E2 set frozen and first run published.** `evals/sets/e2_v1` (50 Lichess-puzzle positions, 25 good and 25 engine-confirmed mistakes), frozen with the three eval prompts and `why_v1` (hashes in its `FROZEN.md`, a test enforces them) **before** any scored run; design and limits in `docs/decisions/0003-e2-eval-design.md`. Runner `evals/tools/run_e2.py`, report generator `report_e2.py`. Cost about 1.9 dollars for the full run (50 items, about 35 s each).
- **Result (claim correctness at depth-18 scoring):** raw 80% (162/202), grounded first draft 93% (151/162), verified 93% (143/154). Texts with a wrong claim: 27, 9, 8 of 50. Unverifiable statements: 243, 71, 68. **The 98% target for `verified` was not met as measured.** The gate repaired 9 of 50 and fell back once. `evals/reports/e2_v1_2026-10-07.md` and `_notes.md` (read the notes first).
- **What the notes say:** most wrong claims in `verified` look like extractor over-reading (7 of 11 are bands or free-piece claims the text never makes), 2-3 are real: **move sequences in the prose are not checked for legality in order**. The scorer is not independent of the verifier, so the `verified` rate says little by itself; the real signal is raw vs grounded (evidence cuts wrong texts from 27 to 9) and that unverifiable statements stay high. No human has reviewed the items or the extractions.
- **Next:** T35 (follow-ups: sequence check, `extract_v2`, human read of a sample, decide on unverifiable statements, GPT baseline, then E2 v2), T21 (E1 rules suite), T22 (README, demo). Do not edit the frozen files; fixes are new versions.
- **Branch / PR:** `feat/e2-eval`

### 2026-10-07 · MacBook · Claude Code (session 21, part 7)
- **T19 done (v1): "What were you considering?"** New **Review** tab: pick a synced game, see up to three key moments (board before the move, what it cost), optionally say what you were thinking, press Compare or Skip. `POST /synced-games/{gid}/moments/{ply}/intent`. Design for eval E4: the model's only job is to say which **fact ids** your answer mentions (`coach/prompts/intent_v1.md`); the facts (free piece available, opponent threats before the move, a piece your move left to be taken, missed/allowed mate) are built by the detectors and rules in `coach/intent.py:moment_facts`, and the "You saw / You did not mention" text is assembled by code from those facts. So a gap statement can only name something really on the board, nothing is claimed about intent the player did not state, and the answer (untrusted data, rule 7) has no text channel through the model. Answers are saved as written, `self_reported: true`, in `data/intents/intents_v1.jsonl` (git-ignored); skipping stores nothing. Without a key the page lists what was on the board instead of comparing.
- **Not yet:** E4 has not been measured (needs the real model, a frozen set of answers, and a count of gap statements naming a real threat); the key-moment facts do not yet include forks or the engine's refutation line; only your own moves; no way to edit or delete a saved answer; no use of saved answers in the blind-spot map.
- **Note:** the live check wrote one test answer to `data/intents/intents_v1.jsonl` ("I wanted to attack the knight"); delete the file if you want a clean start.
- **Review fix (GPT, P2):** the intent endpoint now runs the engine (depth 16, as the review does) to add `missed_mate` / `allowed_mate` facts for the selected moment; before, `1.f3 e5 2.g4` (which allows `Qh4#`) returned no facts and the page said nothing special was on the board. Tests with a fake engine and one with Stockfish.
- **Branch / PR:** `feat/intent-question`, stacked on `feat/coach-harness`. Stack: #34 threats <- #36 verifier <- #35 harness <- this.

### 2026-10-07 · MacBook · Claude Code (session 21, part 6)
- **T18 verifier + T17 coach harness (v1).** `coach/verifier.py` checks structured claims (move legal, line legal, move captures, best move, piece can be taken, free piece available, eval band, mate) against the rules, Stockfish (depth 12) and the detectors, then guards the prose: any move or pawn amount in the text must be backed by verified evidence. `coach/agent.py`: intent (`why_move` only; anything else is refused) -> exact state -> engine/detector evidence pack -> `AnthropicDrafter` (prompt `coach/prompts/why_v1.md`, model `COACH_MODEL`, default `claude-sonnet-5-5`) -> verify -> **one repair attempt** with the failure reasons -> else only verified facts plus a note (`status`: verified / repaired / fallback / unavailable). Versions of prompt, model, verifier, engine budget and detectors are in every result. `POST /games/{id}/coach/why {ply}` (Practice only) and a **Why?** button in the feedback panel. 35 new backend tests with a scripted fake model, 2 web tests.
- **Found by running it, not by the unit tests:** with no credential the SDK raises a bare `TypeError`; it is now caught and reported as `unavailable`.
- **Not yet run against the real model.** `ANTHROPIC_API_KEY` is empty in `.env`; the owner must add it there (never in chat or the repo) before the Why? button shows an LLM explanation; until then it shows the checked facts with a note. The first real run is also the first test of whether the prompt gets claims through the verifier; expect to tune `why_v1` and to bump its version when changed. No eval numbers exist yet (E2, T20).
- **Known limits:** pawn pushes written as a bare square are not treated as moves by the prose guard (the prompt asks for "pawn to e4"); the verifier's engine checks are depth 12 so a claim near the edge of a band can flip between runs; the Why? text and the feedback panel run separate searches, so a pawn cost can differ by about 0.1 between them; refusals fall back to facts and the server-side fallbacks parameter is not used.
- **Dependency added:** `anthropic` 1.11.0 (MIT) with its row in `THIRD_PARTY.md`.
- **Live trial (owner's key, 2026-10-07, claude-sonnet-5-5):** 6 real key moments from recent games, before and after the stricter assertion guard: 6/6 verified first try before; after: 5 verified, 1 repaired (the guard caught an unsupported evaluation statement). About 8k input and 5.5k output tokens per run of six (roughly 6-7 cents). Costs in pawns differ slightly between runs of the same move (depth-12 search is not deterministic). Not measured: usefulness. The closing tips ("next time, look at castling before moving a rook") are generic advice the verifier does not check and are sometimes weak; tightening the prompt on that is open.
- **Branch / PR:** `feat/coach-harness`, stacked on `feat/coach-verifier` (T18), which is stacked on `feat/threat-warning` (PR #34)

### 2026-10-07 · MacBook · Claude Code (session 21, part 5)
- **Threat warning (T34), Practice only.** On your turn a "Watch out" box lists pieces you can lose to a legal capture (the `hanging_own` v2 definition, so an even trade is not a threat but a knight for a pawn is), checkmate the opponent would have if you passed, and check; threatened squares are shaded red. Rules and detector only. Bound to the game and revision it was computed for. Tests: 5 backend, 1 web.
- **Next (owner asked for T17-T19):** T18 verifier, then T17 coach harness, then T19 intent question. **Blocker for live runs: `ANTHROPIC_API_KEY` is empty in `.env` and the `anthropic` SDK is not a dependency.** Plan: the LLM sits behind a small `Drafter` interface so everything is testable without a key; add the SDK (MIT) with a `THIRD_PARTY.md` row; the owner puts the key in `.env` (never in chat or the repo).
- **Branch / PR:** `feat/threat-warning`

### 2026-10-07 · MacBook · Claude Code (session 21, part 4)
- **T33 done (owner asked for it to move up the list): Practice feedback.** After each of your moves in a Practice game the board page shows a verdict (good / small slip / mistake / blunder; bands in `learner/feedback.py`: within 0.5 pawn good, under 1.5 slip, under 3 mistake, 3+ blunder; not scolded for small drops when already winning by 7+), what was right (best move, took a free piece, left nothing hanging) and wrong (free piece ignored, piece left to be taken, missed or allowed mate), the cost in pawns, and a "Show the better move" button that highlights it in green. All facts come from the engine (depth 12) and detectors `hanging_own` v2 / `missed_free` v2; detector claims need engine confirmation; no LLM. `GET /games/{id}/feedback/{ply}` refuses Play games (403 `feedback_not_allowed`, rule 4). The page hides feedback once its move is taken back. 11 new tests.
- **Not yet:** explanation of *why* with a verified line, warnings about what the opponent threatens, feedback on the opponent's replies, feedback for older moves, and feedback is not saved with the game. The depth-12 check can miss things; the verdict is a guide, not a ruling.
- **Review fixes (GPT, 2 P2, reproduced):** feedback is now bound to the game and the exact moves it judged (a different game or line with the same last move no longer shows it; an older move's feedback disappears once a newer move is made), and no pawn cost is shown when a mate score is involved (the 1000 used to rank mates is not an evaluation). 197 backend and 11 web tests.
- **Branch / PR:** `feat/practice-feedback` (based on `main`; touches TASKS.md and HANDOFF.md, so expect a small merge conflict with #32)

### 2026-10-07 · MacBook · Claude Code (session 21, part 3)
- **T16 v1: blind-spot map page.** New `Blind spots` tab (`web/src/Shell.tsx` holds the Play and Blind spots tabs; the game stays mounted so it is not lost). `GET /blind-spots/baseline` (`backend/app/api/blind_spots.py`) serves the frozen results after re-verifying the window; 404 if not frozen, 500 if the window does not match. The page shows 10|0 and 15|10 side by side, two cards each (missed / available with a plain range; own pieces left hanging per 100 moves), a confidence chip, games affected, how many unclear moves were left out, and a caveat that the check is quick (depth 10). Wording lives in `web/src/spotCards.ts` (tested). Not yet: recency windows, context tags, linked examples (spec C2/C4), and no live (new-game) numbers; it shows only the frozen baseline.
- **Check it:** API on any free port, `cd web && VITE_API_URL=http://localhost:<port> pnpm dev`. The API has no `--reload`: restart it after pulling, or `/blind-spots/baseline` returns 404.
- **Branch / PR:** `feat/blind-spot-map`

### 2026-10-07 · MacBook · Claude Code (session 21, part 2)
- **T15 done:** `uv run python -m app.learner.patterns freeze` re-verifies the window, then copies the results to `data/baseline/baseline_results_v1.json` (exclusive create, read-only; refuses to overwrite). sha256 `bbbd9babac37731925005d5ffbed7d8f2e88feee35972a5f1f58261c60952c3e`. Test added (177 total). A change to detectors or evidence means a new version file, never an edit.
- **Review fixes (GPT, 2 P2, reproduced):** #30: `run()` now refuses evidence not made at the baseline budget (depth 10, no movetime) or by mixed engines, and keeps the full budget in the result. #31: `freeze` now validates the exact bytes (valid JSON, results version, window fingerprint, time controls, both detectors, engine budget) before creating the file. 185 tests.
- **Note on the frozen file:** it was frozen before the #30 fix, so its `engine` field uses the earlier layout (`[{engine, depth}]`; movetime was None). The numbers are identical to a fresh run (checked); the hash above stays the record. It was not replaced (deleting it was blocked and it is read-only by design). A re-run writes the new layout to `data/patterns/`.
- **Branch / PR:** `feat/freeze-baseline-results`, stacked on `feat/pattern-layer` (PR #30); base it on `main` once #30 merges.

### 2026-10-07 · MacBook · Claude Code (session 21)
- **T14 done: pattern layer** `backend/app/learner/patterns.py`. Verifies the baseline window against its manifest first, then for each user move builds `Evidence` from the stored depth-10 fast pass (mover's side via `rank_for_mover`) and runs both detectors. Per time control only; uncertain moves leave every numerator and denominator (also the per-100-moves denominator) and are reported separately; labels per spec C3 (`insufficient` / `tentative` at >=3 misses in >=2 games / `established` with >=8 opportunities too); 95% Wilson intervals (optimistic: moves within a game are not independent). `hanging_own` is per 100 moves only. Fails closed if a window game or its analysis is missing or the analysis schema is old. 10 new tests, 176 total, lint clean.
- **Results are in `data/patterns/baseline_patterns_v1.json` and were shown to the owner in chat; the numbers are deliberately not in the repo** (owner's games, public repo). Detector versions: `hanging_own` v2, `missed_free` v2; Stockfish 19, depth 10.
- **Caveat to keep with any figure:** evidence is the depth-10 fast pass, and `uncertain` is 4-5% (hanging_own) and 13-15% (missed_free) of opportunities-or-moves, so rates are lower bounds on confirmed misses, not a measure of all misses. Detectors were scored on `real_play_v1` (see its report); `missed_free` recall on real ignored free pieces is still unmeasured.
- **Next:** T15 (freeze these results in `data/baseline/`, record the hash here), then T16 (blind-spot map page, two time controls side by side).
- **Branch / PR:** `feat/pattern-layer`

### 2026-10-07 · MacBook · Claude Code (session 20)
- **Baseline window frozen** (owner: "freeze it but keep 10/10 and 15/10 coaching ideas separately for now"; "10/10" read as 10|0). Rule: the 100 most recent case-study games by end time; 50 at 10|0 and 50 at 15|10; 30 Aug to 5 Oct 2026. New `backend/app/learner/baseline.py` (`freeze`, `verify`; refuses to overwrite; file is read-only; 7 tests with synthetic games). Written to `data/baseline/baseline_window_v1.json` (git-ignored; **ids never go in the repo**). Fingerprints and the decision are in `docs/decisions/0002-baseline-window.md`; the independent copy that `verify` checks against is `docs/decisions/0002-baseline-window.manifest.json` (hashes and counts only).
- **Time controls kept apart for now:** two separate lists with their own fingerprints; results reported per time control only (no pooled figure); one coaching focus per time control; the map page shows them separately. Reversible: both lists and the whole are frozen, so a pooled figure can be added later.
- **No detector has been run on the baseline games yet.** Next is T14, with results per time control, then T15 (freeze the results).
- **Review (GPT, 2 P2 findings, reproduced, fixed):** `verify` trusted the hashes stored in the file, so a different window or swapped time-control lists passed; it now checks against the committed manifest and fails closed. `freeze` had a check-then-write race (two concurrent freezes both succeeded); creation is now exclusive (`O_EXCL`). 7 tests fail on the old code.
- **Branch / PR:** `feat/baseline-window`

### 2026-10-07 · MacBook · Claude Code (session 19)
- **Licence decided and applied: AGPL-3.0-or-later** (owner: "apply AGPL", on Claude's recommendation: python-chess is GPL-3.0-or-later so MIT is out; AGPL is compatible and covers hosted use; every other dependency is permissive). Added `LICENSE` (official AGPL-3.0 text), `THIRD_PARTY.md` (every direct dependency with version, licence, URL and use; plus Stockfish, the Lichess puzzle data and the Chess.com API), licence fields in `backend/pyproject.toml` and `web/package.json`, and a README section. A scan of all 47 installed Python packages found python-chess is the only copyleft one.
- **Found and fixed:** `httpx` is imported at runtime by the Chess.com sync but was declared only as a dev dependency (it would have broken a production install). Moved to runtime dependencies.
- **Guards (tests):** the LICENSE is the full AGPL-3 text and both project files declare it; every direct dependency has a `THIRD_PARTY.md` row; no copyleft package other than python-chess is installed; runtime imports are runtime dependencies. 153 backend tests.
- **Still open for later:** a contributor agreement before accepting outside contributions; licence notices when a built web bundle is published; a lawyer's check before any commercial launch (nothing here is legal advice).
- **Branch / PR:** `chore/license-agpl`

### 2026-10-06 · MacBook · Claude Code (session 18)
- **T13 done.** `evals/tools/score_detectors.py` scored `hanging_own` v2 and `missed_free` v2 on the frozen `real_play_v1`, static and with engine evidence (Stockfish 19, depth 10 = the production fast-pass budget; the labels' own runs used depth 14). Report: `evals/reports/real_play_v1_2026-10-06.md` (+ `.json`, + `_notes.md`). Nothing was tuned; the detectors and set were unchanged after the first run, and the numbers reproduce exactly on a second run.
- **Headline (point estimates, 95% Wilson intervals in the report):** `hanging_own` v2 precision 42/44 static, 41/42 with evidence; recall 42/42, 41/42. `missed_free` v2 precision 43/44 static, 43/43 with evidence; recall 43/43 both. The spec's E3 targets (precision >= 90%, recall >= 80%) are met by the point estimates; the lower end of the interval for `hanging_own` static precision is 0.85. Uncertain rate: `hanging_own` 2/89, `missed_free` 1/113 (with evidence).
- **Do not quote those as real-play performance.** They measure detection accuracy on curated puzzle positions and hand-built positions, against labels that share the detectors' material definition. `missed_free` has **no real missed examples** in the set (puzzles only show correct solutions), so its recall on real ignored free pieces is unmeasured. Reviewed labels: 82 of 202 items, no strong human player.
- **The 4 disagreements are 3 items; none is a detector logic error:** rp1-080 (static cannot know the engine disagrees: intended), rp1-095 (the label sits on the 100 cp threshold: loss 98 at depth 14, 237 at depth 10), rp1-128 (already-winning position: at depth 10 the engine reports no loss from hanging a knight, so the pipeline abstains). **Product implication: real misses made in already-lopsided positions will be counted as `uncertain`, not `missed`.** Expect it in T14.
- **Next:** T14: run both detectors over the owner's last 100 case-study games (`hanging_own` per 100 moves; `missed_free` as missed/available plus per 100 moves), using the stored fast-pass analysis (schema 2, depth 10) as evidence. The baseline must be frozen (T15) before the coach is used on the owner's games; running the detectors for T14 is the baseline measurement itself, so freeze the game window first.
- **Branch / PR:** `feat/t13-score-detectors`

### 2026-10-06 · MacBook · Claude Code (session 17)
- **Second reviewer (GPT) result:** 52 items, 51 agree, 0 disagree, 1 undecided (rp1-022, mate question "can't tell"). python-chess on all 52; Stockfish 19 depth 18 on 29 (22/22 and 29/29 agree). The comparison script was sanity-checked by corrupting answers (it found exactly the corrupted ones).
- **real_play_v1 FROZEN** (decision made by Claude under the owner's delegation, reversible via v2). **Deviation, stated in the frozen files:** the owner's raw result did not meet the pass rule as written (5 > 3, one kind); frozen because each of the 5 was adjudicated by the independent search (label supported 5/5) and GPT found no disagreement. 82 of 202 items had some review, no label error found, but no strong human player has reviewed it. FROZEN.md has the hashes; the builder refuses to overwrite a frozen set.
- **Owner's check without the engine** (confirmed by the owner).
- **Next:** write the precision/recall script and run `hanging_own` v2 and `missed_free` v2 on the frozen set (static-only and with engine evidence), publish in `evals/reports/` with versions, denominators, 95% Wilson intervals, split real/constructed and with/without mate themes. Do not change the detectors or the set to improve the numbers; report what comes out.
- **Branch / PR:** `feat/handcheck-page` (PR #24)

### 2026-10-06 · MacBook · Claude Code (session 16)
- **Owner's hand-check result:** 30 items, 25 agree, 5 disagree, 0 "can't tell". Strata: real_taken 9/9, no_opportunity 4/4, real_safe 6/6, real_blunder 5/5, constructed_miss 1/6. All 5 disagreements are constructed misses where the owner said no free piece. **Pass rule as written (at most 3, no pattern) is NOT met; recorded as a fail.** Adjudicated with the independent exchange search (not a detector): the label is supported in 5 of 5 (four captures that also mate, net +5; one king capture of an undefended knight, net +3), so the checker missed easy-to-overlook captures, not a label error. The adjudication step was added after seeing the results, and is stated as such in `LABEL_RULE.md` section 9; both numbers are reported from now on. `evals/tools/compare_handcheck.py` does the comparison; answers are in `handchecks/owner_answers.txt`.
- **Not frozen yet.** Still needed: the second reviewer (full three-question sheet `handcheck_second.md`, plus all 22 adversarial items), then the freeze decision. Only 30 of 202 items have human review, by a checker rated under 1000.
- **Owner's answers were given without the engine** (confirmed by the owner), so no tool-assisted split is needed for them.
- **Next:** send `handcheck_second.md` to GPT with `evals/sets/real_play_v1/handchecks/second_reviewer_prompt.md` (the answers file `positions.jsonl` is in the same repo, so GPT must be told not to read it, and any tools it uses must be reported); compare with a script extension for the A/B/C format, then freeze, then run the detectors.
- **Branch / PR:** `feat/handcheck-page` (PR #24)

### 2026-10-06 · MacBook · Claude Code (session 15)
- **Done:** the owner found the hand-check sheet too hard to read and answer (notation, links, abstract questions). Replaced it for the owner with `evals/sets/real_play_v1/handcheck_owner.html`: a self-contained page with the board, the move as an arrow, the move in plain words, and at most two yes / no / can't tell questions per item (B appears only when A is yes). Same 30 items, labels hidden, answers saved in the browser, a Copy button that produces lines like `rp1-201: A yes, B no`. For `hanging_own` items it shows the board after the move. The second reviewer keeps the full three-question sheet.
- **Next:** owner opens the page and answers (can't tell is fine), pastes the copied text; compare against `material_label` using the mapping in `LABEL_RULE.md` section 9; then the second reviewer; then freeze and run the detectors. A comparison script is not written yet.
- **Branch / PR:** `feat/handcheck-page`

### 2026-10-05 · MacBook · Claude Code (session 14)
- **Done:** added **ADR 0001** (`docs/decisions/0001-open-source-reuse.md`, from the owner's file): what to reuse and under what rules (Lichess CC0 data, Maia-2, ChessBench; read Chesskit/others, do not fork). Checked it against the repo and licences, and corrected it in place with marked amendments (section 6): (A1/A2) the puzzle `FEN` is the position **before** the opponent's move, so `hanging_own` already has its position and `missed_free`'s opportunity is after `Moves[0]`; (A3) the games sample is deferred to v2 (a month is about 28 GB); (A4/A6) set and data locations; (A5) berserk is GPL-3.0, freechess has no stated licence (copy nothing), Lucas Chess is archived; (A7) the licence is still undecided.
- **Tasks:** T13, T14b, T24, T25 now reference the ADR; added T27 (miss-likelihood model), T28 (Maia-2 opponent), T29 (optional board upgrades after T24). T24 now includes `LICENSE` and `THIRD_PARTY.md` (ADR rule 1 is already overdue for the dependencies added so far).
- **Next:** unchanged: the owner's hand-check of `handcheck_owner.md` and GPT's of `handcheck_second.md`, then freeze, then the detector run.
- **Branch / PR:** `docs/adr-0001-open-source-reuse` (stacked on `feat/t13-build-real-play-set`; merge #21 first)

### 2026-10-05 · MacBook · Claude Code (session 13)
- **Done:** T13 label rule decided and merged (the owner delegated the decisions; each is reversible, see `LABEL_RULE.md` section 12). Built `evals/sets/real_play_v1` as a **draft**: 202 items (180 real from Lichess puzzles, 10 per rating band per stratum from distinct puzzles; 22 hand-built adversarial), Stockfish 19 at depth 14, seed 20261007. **No detector has been run on it** and the builder imports nothing from `app/detectors/` (a test enforces this). Item ids are shuffled so they do not reveal the label. 70% of real items carry a mate theme and are tagged for separate reporting. Hand-check sheets (labels hidden) are in the set folder.
- **Next, in this order:** (1) hand-check: the owner answers what they can on `handcheck_owner.md` ("can't tell" is allowed), a second reviewer such as GPT does `handcheck_second.md`; pass rule at most 3 of 30 disagreements, else v2. (2) Freeze: record the sha256 of `LABEL_RULE.md` and `positions.jsonl` here. (3) Write the precision/recall script and run both detectors; publish with versions, denominators and 95% Wilson intervals, split by real/constructed and with/without mate themes.
- **Caveat:** labels are not human-reviewed yet. Do not claim otherwise, and do not run the detectors on this set before step 2.
- **Second round on PR #21 (2 P2 comments, reproduced; rule v0.4):** `real_blunder`/`real_safe` ignored the safe-versus-hanging choice (12 blunders had no safe alternative; 2 safe items had nothing that could hang) and blunders were labelled `missed` on material alone (8 of 40 had engine loss under 100 cp). Now: real hanging_own items need the choice; blunders are `missed` (loss >= 300), `uncertain` (< 100) or excluded; engine numbers are stored; items carry `material_label` for the hand-check. The set was **re-drawn**, so `handcheck_owner.md` and `handcheck_second.md` changed again: use the versions on `main`/this branch, not any earlier copy.
- **GPT review of PR #21 (3 P2 comments, all reproduced):** `no opportunity` was defined by the engine's preferred move (6 items had a legal capture that wins material); the negatives skipped the theme exclusions (1 item); the hand-check questions could not distinguish `taken`, `missed` and `uncertain`. Fixed in rule v0.3: every label now rests on an independent full exchange search in the builder (it also exposed 3 `real_safe` items that hung a piece, which the review had not found). Old set: 10 of 202 items inconsistent; rebuilt set: 0. Tests now enforce the exclusions and the material consistency of every stored item.
- **Branch / PR:** `feat/t13-build-real-play-set`

### 2026-10-05 · MacBook · Claude Code (session 12)
- **Done:** read https://lichess.org/source and checked each repo's real license. CC0: puzzle/games/evaluation databases, `chess-openings`. AGPL-3.0: lila, lichess-puzzler, database tools, api docs. GPL-3.0: chessground, chessops, pgn-viewer, stockfish-web, fishnet, berserk. MIT: scalachess (Scala, not useful). We reuse **data only**; for Lichess sync call the HTTP API with `httpx` rather than the GPL `berserk` client.
- **Licensing finding:** the backend depends on `python-chess` (GPL-3.0-or-later), so the repo should be GPL-3.0+ or AGPL-3.0+, not MIT (T24 reworded; owner to decide).
- **Downloaded (owner-approved, git-ignored):** `data/lichess/lichess_db_puzzle.csv.zst`, 293 MB. 6,157,341 puzzles; 224,023 tagged `hangingPiece`; **91,638 rated 400-1200** (400-599: 15,097; 600-799: 19,638; 800-999: 28,312; 1000-1199: 28,464; a few at 1200). Added `zstandard` as a dev dependency to read it. Games files were **not** downloaded: one standard month is ~28 GB compressed.
- **Format notes for T13:** columns `PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity, NbPlays, Themes, GameUrl, OpeningTags, DailyDate`. `FEN` is the position *before* the opponent's last move; `Moves[0]` is that move (a real human blunder), then the solver's moves follow. So `(FEN, Moves[0])` is a real-game positive for hanging_own, and the position after `Moves[0]` with solution `Moves[1]` is a real opportunity for missed_free. Puzzles only give correct solutions, so negatives (a player who missed the capture, a safe move) need other sources.
- **Next:** agree T13's label rule with the owner before writing any code, then freeze it before running the detectors; owner hand-checks about 30 labels.
- **Branch / PR:** `docs/lichess-data-and-license-notes`


### 2026-10-05 · MacBook · Claude Code (session 11)
- **Done:** a GPT full-repository audit (`~/Documents/full-code-review.md`) gave 7 findings; all 7 reproduced, fixed and merged (#14 to #17), each answered on its original PR. (1) null move skipped a turn: moves must be in `legal_moves`. (2) concurrent moves both applied: per-game lock; the engine search runs outside it and is applied against the revision captured before thinking. (3) draw declared on a prospective claim: automatic rules plus actual repetition/fifty-move. (4) a checkmated position lost its winner (correct mating move shown as a blunder): `Score.mate_sign`, stored in positions. (5) stale analysis reused: records carry `schema` and are reused only when schema, engine and budget match. (6) resignation undone by a late engine snapshot: `acceptGame()` in the web app; a mode change now bumps the server revision. (7) pinned defenders could recapture: `see()` plays legal moves; both detectors reflect it.
- **Data:** the local analysis cache was refreshed for all 450 games (schema 2). 189 of them end in checkmate, so the mate bug was on a common path. Anyone with an older cache must re-run `cd backend && uv run python -m app.engine.batch`.
- **Process note:** deleting the base branch of a stacked PR closes the stacked PR automatically (happened to #10). Rebase the stacked branch onto `main` and open a new PR instead.
- **Next:** T13 **as rewritten in `TASKS.md`** (real-play positions, frozen label rule, adversarial cases; see the external review entry below). Then Day 5.
- **Branch / PR:** `docs/handoff-after-audit`

### 2026-10-05 · Cowork review · Claude (external review, no code changes)
- **Reviewed:** whole repo at `5ccaf90`. 98 tests pass and ruff is clean without Stockfish (21 engine tests skipped, so CI with Stockfish is needed).
- **Findings:**
  1. `hanging_own` opportunity ("some move hangs, some move does not") holds in almost every position, so missed/available ≈ missed per move. Report per 100 moves, or tighten (e.g. a piece is already attacked).
  2. Draft eval sets are weak-engine self-play; T13 should use real positions (Lichess puzzles `hangingPiece` 400–1200, Lichess rapid 600–1000) with adversarial cases.
  3. No LICENSE file: a public repo without one is "all rights reserved".
  4. Engine tests only run where Stockfish is installed; add CI.
- **Lichess reuse decided:** CC0 puzzle, games and evaluation databases (eval sets, peer benchmark, practice bank). Main Lichess codebase (lila) not reused.
- **Tasks changed:** T13 rewritten; T14 split by detector; added T14b, T23, T24, T25, T26.

### 2026-10-05 · MacBook · Claude Code (session 10)
- **Done:** merged T12 (missed_free, with the two GPT-review fixes). `hanging_own` v2 (legal captures only, version bumped). On the draft set the `hanging_own` smoke numbers moved from 20/22 and 20/25 to 21/23 and 21/25; the set has no pin-focused positions, so this says little.
- **Next:** T13, on fresh seeded sets with frozen label rules **including adversarial cases** (pinned capturers, losing captures, several capturers on one target). Report each detector's version with its numbers.
- **Branch / PR:** `fix/hanging-own-legal-captures`

### 2026-10-05 · MacBook · Claude Code (session 9)
- **Done:** T12. `detectors/missed_free.py` (v1) and a 50-position draft set (`evals/sets/missed_free_v1/`, builder `evals/tools/build_missed_free_set.py`). Also web: engine reply is shown 1 s after the player's move (`ENGINE_MIN_REPLY_MS`). Takeback rule confirmed by the user: 2 undos per move (a new move resets the allowance), which is what is implemented.
- **GPT review of PR #12 found two real `missed_free` bugs** (losing capture credited as taken; pinned attacker creating a free piece). Both fixed with regression tests; each legal capture is now evaluated on its own (`see.capture_net`). The draft set gave the same numbers before and after, so it cannot catch this class of bug: the T13 set needs adversarial cases (pins, losing captures, several capturers).
- **Smoke check only:** 24/24 `missed` calls correct, 24/25 misses found on the draft set. The set is easy; do not quote.
- **Process:** `REVIEW.md` and the PR template with a Reviewed-by section are merged. `hanging_own` had the pinned-attacker weakness; fixed as v2 in `fix/hanging-own-legal-captures` (PR open), version bumped, regression tests added.
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
