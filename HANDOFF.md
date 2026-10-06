# HANDOFF.md

Update this at the end of every session (any agent, any machine). Newest entry on top. Keep each entry short.

---

## Current state

- **Phase:** Week 1, Day 4 done: T13 complete (set frozen, detectors scored); Day 5 (T14: run the detectors on the owner's games) is next
- **Active branch:** `feat/t13-build-real-play-set` (PR into `main`)
- **Machine/agent last used:** MacBook / Claude Code
- **Detector versions:** `hanging_own` v2, `missed_free` v2 (both: legal captures and legal recaptures). Analysis record schema: 2. Report these with any number.
- **Baseline frozen?** No (planned Day 5 — do not use the coach on own games before this)
- **Frozen eval sets:** `evals/sets/real_play_v1` (frozen 2026-10-06). sha256: positions.jsonl `d3b44968...33bf`, LABEL_RULE.md `2f454c57...2ec6`, provenance.json `aefade53...87b3`; full hashes in `evals/sets/real_play_v1/FROZEN.md`. A test fails if they change.

## Next up

1. Day 4: T13 (rewritten): fresh, frozen set from real play (Lichess puzzles + Lichess rapid games), adversarial cases, label rule frozen first, ~30 labels hand-checked.
2. Day 5: T14 (hanging_own per 100 moves; missed_free as missed/available), T14b peer benchmark, T15 freeze baseline, T16 blind-spot map page.
3. Housekeeping: T23 CI with Stockfish, T24 LICENSE (before sharing the repo widely).

## Blockers / open questions

- **Licence not chosen (T24):** python-chess is GPL-3.0-or-later, so the repo should be AGPL-3.0 or GPL-3.0, not MIT. ADR 0001 proposes AGPL-3.0; the owner decides. No `LICENSE` or `THIRD_PARTY.md` yet.
- ~~Baseline game count~~ resolved: 450 case-study games available (253 at 10|0, 197 at 15|10), 4 Jul – 5 Oct 2026. Enough for a 100-game baseline; the window still needs choosing before Day 5 freeze.
- Fast-pass evaluations are not yet flagged as uncertain when unstable (spec B2); needs a second-depth comparison.
- Reviews are not cached; each call re-runs the deep check (a few seconds).
- The per-game lock is in-process only. Several backend workers would need a database-level guard (plan it with Postgres).
- Web has unit tests for the response-ordering rule (`pnpm test`) but no component or browser integration tests.
- Draws end only when reached (actual threefold repetition, fifty-move clock, automatic rules). Players cannot claim a draw yet.
- Both draft eval sets are easy, engine-labelled and unreviewed. A human spot-check of labels is still owed before anything is frozen.

---

## Log

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
