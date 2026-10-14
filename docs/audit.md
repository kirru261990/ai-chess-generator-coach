# Step 0 audit: the repo against PRD v2

**Date:** 2026-10-13 · **PRD:** `docs/prd-v2.md` (copied from the owner's file, unchanged) · **Repo at:** `main` `10216d0`
**Status:** waiting for the owner's review. No feature code has been written for PRD v2.

---

## 1. Summary in plain words

- **About 60% of what PRD v2 needs exists already**, mostly at the bottom of the system: the Chess.com sync, the Stockfish
  wrapper, the two mistake detectors (hanging piece and missed free capture), the verifier that checks the coach's words, the
  hand-check page, the board and the hint card in the web app.
- **The two features themselves do not exist yet:** Replay My Mistakes (Feature A) and the unassisted assessments (Feature B).
  There are no pools, no assessments, no sessions, no tap-a-square step and no Progress screen.
- **Five things conflict** with how the repo works today. Each needs your decision (section 6). The biggest are:
  1. **Nothing is saved to a database.** Games live in memory and in files. The PRD needs a real database. I recommend SQLite.
  2. **The detectors are looser than the PRD's definitions.** I recommend new detector versions (v3) that follow the PRD.
     The old v2 numbers stay frozen and untouched.
  3. **There is already a frozen "before" window** of 100 games (7 Oct). The PRD wants a different one: the last 30 games per
     time control, frozen when your first practice session starts.
  4. **You have already seen some of your own positions** on the hand-check page. Those must not be used as "unseen" test positions.
  5. **I found one gap in the PRD itself:** a CLEAN position can hide a real free piece. The fix is in section 5.
- **There are enough positions.** Based on the frozen 100-game numbers, your 450 games should hold several hundred hanging
  pieces and about 200 missed free captures. That is well above the 16 + 8 held-out positions the PRD needs per type. The
  stricter PRD thresholds will cut this. Step 1 measures the real count.

---

## 2. What exists (reuse it)

| PRD need | What the repo has | File | Fit |
|---|---|---|---|
| Chess.com import, 10-min and 15+10 | Serial sync with a contact User-Agent. It deduplicates by game URL. 450 games so far (253 at 10\|0, 197 at 15\|10, 4 Jul to 5 Oct). | `backend/app/sync/chesscom.py`, `config.case_study_time_controls()` = `600,900+10` | Good. It is command-line only today, so the "Sync games" button and the sync at app start are missing. |
| Stockfish wrapper | One process, a lock, scores turned to one side's view, mate kept apart from centipawns, engine name and search depth recorded | `backend/app/engine/stockfish.py`, `shared.py` | Good base. Short of the PRD (section 3). |
| Per-game analysis cache | A JSON-lines file. Each game is redone when the engine name, depth or record layout changes. | `backend/app/engine/batch.py` (`AnalysisStore`) | Partial. It is keyed by game, not by (position, engine config). |
| M1 hanging piece | `hanging_own` v2: legal captures only, net gain ≥ 2, engine confirms a loss ≥ 100 cp, unsure cases left out of both counts | `backend/app/detectors/hanging_own.py` | Close. Thresholds and checks differ (section 3). |
| M2 missed free capture | `missed_free` v2, mirror of the above | `backend/app/detectors/missed_free.py` | Close. Same differences. |
| Exchange maths | Per-capture static exchange with legal recaptures | `backend/app/detectors/see.py` | Reuse. |
| Detector precision check | Frozen `real_play_v1` set. `hanging_own` precision 38/39 on real positions with evidence. `missed_free` had **no real misses** in the set. | `evals/reports/real_play_v1_2026-10-06.md` | The PRD's 27/30 gate is a new check on the new detectors. |
| Hand-check page for the owner | Board, arrow, plain words, Yes / No / Can't tell, a Copy button | `evals/tools/make_handcheck_page.py`, `compare_handcheck.py` | Reuse for the Step 1 gate (30 positions). |
| Explanations checked against facts | Coach harness, versioned prompts, verifier v2 (legal moves, lines, hanging/free claims, prose check), one repair attempt, then facts only. Budget guard. | `backend/app/coach/` | Strong. The PRD check is narrower and needs bare squares too (section 3). |
| Rates with denominators, unsure cases left out | Miss rates per time control, Wilson intervals, labels | `backend/app/learner/patterns.py` | Reuse for real-game tracking. |
| Shared service layer for web and MCP | `api/tools.py` is called by FastAPI routes and the MCP server | `backend/app/api/tools.py`, `mcp/server.py` | The pattern is right. MCP has only `get_game`. |
| Assisted vs unassisted | Rule 4 and ADR 0005. Practice is `assisted` for good. Help endpoints return 403 in Play. One gate in the page (`feedbackToShow`). | `docs/decisions/0005-practice-assistance.md`, `web/src/gameState.ts` | Same idea as the PRD. Reuse the pattern for assessments. |
| Board, hint card, feedback text | `react-chessboard` board with square styles and move dots, the 5-step hint card, the verdict line, the evaluation bar | `web/src/App.tsx`, `EvalBar.tsx`, `hintRequest.ts` | Reuse the board and the hint card. The evaluation bar must not appear in the new screens. |
| Tests | 658 backend (1 skipped), 55 web. Ruff and tsc clean. | | The suite passed on 2026-10-13. |

## 3. What exists but falls short of the PRD

| PRD item | Today | Gap |
|---|---|---|
| §4.1 Pinned Stockfish build | Homebrew `stockfish` 19 on this Mac. The cloud and second-machine runs have used **Stockfish 16**. | Nothing pins the build. Record the binary's hash with the version, or refuse to run on a different build. |
| §4.1 Recorded engine config | Only the engine name and depth (and movetime) are recorded. | Add network, MultiPV, hash, threads, score perspective. Add an `engine_config` id. |
| §4.1 Depth ≥ 18, MultiPV 3 | Depths used: 10 (fast pass), 12 (feedback, hints, verifier, eval bar), 16 (review). MultiPV is never set. | New "evidence" config at depth 18, MultiPV 3. Keep depth 10 only to find candidates. |
| §4.1 Cache by (FEN, config) | Cache by game | Add a position-level cache (a database table). |
| §4.2 Thresholds | Material ≥ 2 pawns (PRD 3). Engine loss ≥ 100 cp (PRD 200 for M1, 150 for M2). Already-lost cut at −700 (PRD ±600, both sides). No minimum ply (PRD 8). | New constants exactly as the PRD lists them, in one file, with versions. |
| §4.3 M1/M2 definitions | Static exchange on the board after the move. Pawns are never counted as victims. | The PRD needs the refutation **in the engine's top line**, within 4 plies, and (for M2) the best move or an equal one to be the capture. Pawns can only reach the 3-point minimum together with other material, so leaving them out mostly holds. |
| §4.5 Reliability | Unsure cases are left out when the engine does not confirm a loss. | Add: the loss holds at depth 18 **and** depth 14, the move was not the only legal move, the position is not decided. |
| §4.4 Sound move | The feedback route grades a move against the best move at depth 12. | New validator with the PRD's rules, the same evidence config, and any legal move checked on demand. |
| §4.7 Evidence record | The facts are spread across the analysis records and the detector results. | One stored record per MISTAKE position with the PRD's fields. |
| §6.3 Hint ladder | 5 steps for a **live game vs Stockfish** (Think, Idea, Piece, Why, Move), built from the engine's best move. | The PRD ladder is 3 steps built from the evidence record (last move, piece at risk, refutation). Reuse the card, new content. The live-game ladder stays as it is. |
| §12 Output check | `check_prose` checks moves and pawn amounts. **Bare squares are not checked** (a documented limit). | The PRD rejects any square not in the record. Add a square check plus a template fallback built from the record. Coach prompt gets a new version. |
| §8 Sync button / app-start sync | Command line only | Add `sync_games` to the service layer and a button. |
| §11 MCP | `get_game` only | Step 5. |

## 4. What is missing (new work)

- **Database** (§10): none. `api/store.py` is an in-memory dict. Data lives in git-ignored JSON-lines files under `data/`.
- **Pools** (§5): no PRACTICE/HELDOUT split, no exposure status, no pool-size check.
- **CLEAN position selector** (§4.6).
- **Assessments** (§7): baseline, delayed (72 hours, one pending per type), cued, random order, no going back, reveal only after the last position, resume.
- **Practice sessions** (§6): 5 positions, tap-a-square recognition, move check, feedback with the refutation on the board, Retry/Next, summary, resume.
- **Scoring with random-guess rates** (§7.5).
- **Progress screen** (§7.6), **Home screen** with pool counts and due dates (§9).
- **Real-game tracking with PRD windows and floors** (§8).
- **Leak tests** (§6.5, §11): no response-shape tests exist for these endpoints because the endpoints do not exist.
- **Owner identity**: there is no sign-in. The PRD allows a fixed single user.

## 5. Conflicts and gaps (decision needed or a fix proposed)

### C1. Database. PRD: "use the existing database, else SQLite". AGENTS.md: Postgres.
Postgres is the chosen stack, but Docker is not installed and nothing uses a database (T30 is open). The PRD rule falls back to
SQLite. **Recommendation: SQLite through the Python standard library** (`sqlite3`, no new dependency, no licence row). Use one
small data-access module so a move to Postgres (T30) stays a contained change. This changes the stack table, so it needs an ADR.

### C2. Where decisions are written. PRD: `docs/decisions.md`. Repo: one ADR per file in `docs/decisions/NNNN-title.md`.
**Recommendation:** keep the repo's ADR folder. Add one ADR that adopts PRD v2 and lists every calibrated threshold.

### C3. Detector versions.
The frozen baseline results (`data/baseline/baseline_results_v1.json`) and `real_play_v1` scores are for `hanging_own` v2 and
`missed_free` v2 at depth 10. They must not be edited. **Recommendation:** build the PRD detectors as new versions (`hanging_own` v3 =
M1, `missed_free` v3 = M2) with the evidence config. v2 stays in place for the live Practice game (board marks, hints, verifier)
until it is moved on purpose. Old and new numbers are never compared (PRD §4.1).

### C4. The "before" window. ADR 0002 (frozen 2026-10-07, 100 games, 50 + 50) vs PRD §8 (last 30 games per time control, frozen when the first practice session for a mistake type starts).
They measure different things and use different detectors and engine settings. **Recommendation:** keep ADR 0002 as the historical
record, never edited. Add the PRD windows as new rows (`baseline_window` per mistake type and time control), analysed with the v3
detectors and the evidence config. Note that the newest synced game is from 5 Oct, so sync before freezing.

### C5. Positions you have already seen.
**Correction (2026-10-13, Step 1b):** the premise below is wrong. `real_play_v1` holds Lichess puzzles and constructed positions, none from your games, so no position is excluded today. See ADR 0006, decision 5.

You answered the hand-check page for 30 `real_play_v1` positions, and the Review tab showed key moments of synced games. Positions
that come from your own games and that you have already studied are not "unseen". **Recommendation:** any position whose game is in
`real_play_v1` is excluded from HELDOUT assessments (`e2_v1`/`e2_v2` are Lichess puzzles, not your games). The game keeps its pool, and those positions stay usable in
practice. I would not exclude every game the Review tab could show: you used it rarely and it is hidden now. Tell me if you see it
differently.

### C6. PRD gap: a CLEAN position can hold a real free piece (§4.6).
As written, a position is CLEAN when your move was sound and some piece is attacked. If you *took* a free piece there, your move was
sound, so the position is CLEAN, yet "No immediate threat" would be the wrong answer. **Proposed fix:** a CLEAN position must also
have no M1 or M2 opportunity at the evidence config: none of your pieces can be won for ≥ 3 points, and you have no capture
winning ≥ 3 points. This tightens the definition without changing any number.

### C7. Smaller points to settle (my proposed reading, in brackets)
- **`MIN_PLY` = 8**: is that 8 half-moves (move 5) or 8 full moves? *(8 half-moves, i.e. from White's 5th move.)*
- **Recognition chance** (§7.5): when there are two target squares, the chance is 2 ÷ (pieces + 1), not 1 ÷ (pieces + 1). Only
  pieces can be tapped. *(Count all targets. Allow taps on pieces only.)*
- **Sound move rule 3 vs rule 4** (§4.4): rule 4 (loss ≤ 100 cp) applies to every move, so "captures the free piece" in rule 3
  never saves a capture that loses more than 100 cp. *(Read as written: a capture must also pass rule 4.)*
- **"Stratified by time control"** (§5.1) with a fixed hash: a strict 60/40 split per time control would move games between pools
  as new games arrive, which §5.1 forbids. *(Hash of the game id mod 100 < 40 means HELDOUT. That gives 60/40 on average in each
  time control, and a game never changes pool. Report the real split.)*
- **Refutation within 4 plies** (§4.3): material is measured along the engine's top line. A line that stops mid-exchange could
  overstate the swing. *(Count the material after the line, then require the last capture square to be safe by static exchange.)*
- **Spec D3 to D5** (2 own + 2 curated + 1 held-out per session, fading scan prompts) is replaced by PRD v2. *(Mark those rows as
  replaced in `docs/spec.md` and point to the ADR. The T44 and T25 tasks change accordingly.)*
- **Model spend**: October's ledger shows 8.85 of the 10-dollar budget used (9 Oct). LLM explanations in Step 3 will mostly fall
  back to the template until the budget is raised. That is safe, but you will see fewer worded explanations.

## 6. Decisions for the owner

Answer each one with "yes" or with your change.

1. **Database: SQLite** (C1)?
2. **Decisions in `docs/decisions/` ADRs**, not one `docs/decisions.md` (C2)?
3. **New detector versions v3** for M1/M2; v2 stays frozen and keeps running the live Practice game (C3)?
4. **Keep the 7 Oct baseline as history** and add the PRD windows alongside it (C4)?
5. **Exclude positions you have hand-checked or seen in the eval sets** from held-out tests (C5)?
6. **The CLEAN-position fix** in C6? It adds a rule but changes no PRD number.
7. **The readings in C7**?

## 7. Proposed plan (the PRD build sequence, mapped to this repo)

Each step is one or more PRs into `main`, built in a separate `git worktree` so the folder your dev server uses stays on `main`.

| Step | Work | Exit gate (from the PRD) |
|---|---|---|
| 1a | ADR 0006 (adopt PRD v2, SQLite, decisions above). SQLite schema module (§10). Pinned engine config with a recorded binary hash. Position cache. | Tests for the cache and for refusing a mismatched engine. |
| 1b | `hanging_own` v3, `missed_free` v3, sound-move validator, CLEAN selector, evidence records. Thresholds in one versioned file. A command to run them over all synced games. | |
| 1c | A hand-check page with 30 flagged positions (reuse `make_handcheck_page.py`). You answer it. Thresholds are calibrated and recorded in the ADR. | **At least 27 of 30 are real mistakes.** |
| 2 | Pools (hash split, exposure status, pool-size check), the baseline assessment (backend, then the screen), scoring with random-guess rates, PRD real-game windows. | A baseline works end to end. A test proves held-out positions only leave through the assessment endpoints. |
| 3 | Replay My Mistakes: sessions, tap-a-square, move check, 3-step hints, feedback with the output check, summary, resume. | One full session works. The leak test passes. Resume works. |
| 4 | Delayed assessments (72 hours, one pending per type), the results reveal, the Progress screen, real-game rates with floors. | A delayed assessment appears after 72 hours with no position seen before. Progress shows practice and assessment results. |
| 5 | MCP tools over the same service layer. | Later. |

**Rough engine cost of Step 1b:** the depth-10 pass already exists for all 450 games. It finds the candidates (about 4 of every 100
moves for M1). Only candidates and CLEAN candidates get the depth-18 and depth-14 checks, so a few thousand positions in all. I
expect under an hour on this Mac. I will measure it before running everything.

**What the PRD leaves alone:** the Play/Practice game against Stockfish, its hint ladder, evaluation bar and badges stay as they
are. The Review and Blind spots tabs stay hidden.
