# HANDOFF.md

Update this at the end of every session (any agent, any machine). Newest entry on top of the Log. Keep each entry short.

---

## Start here (new session)

1. `cd ~/Projects/ai-chess-generator-coach`. Read `AGENTS.md`, this file, then `REVIEW.md`. Spec: `docs/spec.md` (v0.4). Open decisions: `docs/decisions/0001-open-source-reuse.md`.
2. **No PRs are open** (PR #25, the T13 scoring and the documents, is merged). Work from `main`: `git checkout main && git pull`.
3. Check the machine: `cd backend && uv sync && uv run pytest -q && uv run ruff check .` should pass with clean lint (**176 passed** on 2026-10-07; the count grows as tests are added). `cd ../web && pnpm install && pnpm test && pnpm exec tsc -b`.
4. Take the next task from "Next up" below, on a branch `feat/<name>` or `fix/<name>`, one task per PR.

## Current state

- **Phase:** Week 1, Day 4 done. T11, T12 and T13 are complete (two detectors, a frozen real-play eval set, first scores). Day 5 (T14: run the detectors on the owner's own games, T15 freeze the baseline) is next.
- **Branches:** everything is on `main`; no open PRs.
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
