# ADR 0006: Adopt PRD v2 (Replay My Mistakes and unassisted assessments)

**Status:** Accepted 2026-10-13 · **Decided by:** the owner ("okay, proceed" on the Step 0 audit, after asking why a database
is needed), on Claude's recommendations in `docs/audit.md` section 6
**Related:** `docs/prd-v2.md`, `docs/audit.md`, ADR 0002 (the 7 Oct baseline window), ADR 0005 (Practice assistance)

## Decision
PRD v2 is now the plan for the coaching loop. It replaces spec rows D3 to D5 (training sessions, hint ladder, fading scan
prompts) and tasks T44 and T25 as they were scoped. The live Play/Practice game against Stockfish, with its hints, evaluation bar
and badges, stays as it is (ADR 0005).

The seven audit decisions, all accepted as recommended:

| # | Decision | Why | To reverse |
|---|---|---|---|
| 1 | **SQLite** (stdlib `sqlite3`, `data/coach.sqlite3`) holds PRD v2 data. Postgres stays the later target (T30). | The PRD needs data that survives restarts (72-hour tests, exposure, pools, resume, history) and all-or-nothing writes. Docker is not installed. No new dependency. | Port `app/db/schema.py` and `app/engine/evidence.py` (the only SQL) to Postgres |
| 2 | Decisions stay in `docs/decisions/NNNN-*.md`, not one `docs/decisions.md`. Calibrated thresholds go in this ADR. | One convention in the repo | n/a |
| 3 | PRD detectors are **new versions** (`hanging_own` v3 = M1, `missed_free` v3 = M2). v2 stays frozen with its results and keeps running the live game. | Frozen numbers must not change. Results from different configs are never compared. | n/a |
| 4 | The 7 Oct window (ADR 0002) stays as history. PRD windows (last 30 games per time control at the first practice session for a type) are new rows in `baseline_window`. | They measure different things with different detectors | n/a |
| 5 | ~~Positions from games in `real_play_v1` are excluded from assessments.~~ **Corrected 2026-10-13 (Step 1b): `real_play_v1` holds Lichess puzzles and constructed positions, none from the owner's games, so this excludes nothing today.** The `position.excluded_reason` column stays for any owner game the owner is later shown outside an assessment. | The audit's premise was wrong; found while building Step 1b | n/a |
| 6 | A CLEAN position must also have **no M1 or M2 opportunity** (no own piece losable for ≥ 3, no capture winning ≥ 3), at the evidence config. | Otherwise "No immediate threat" can be the wrong answer to a CLEAN position (audit C6). No PRD number changes. | Drop the extra rule |
| 7 | Readings: `MIN_PLY` = 8 half-moves. Recognition chance counts every target square: targets ÷ (pieces + 1). Taps on pieces only. Sound-move rule 4 applies to captures too. Pool = HELDOUT when sha256(game id) mod 100 < 40 (about 60/40 in each time control, never changes; the real split is reported). Refutation material is counted along the engine's top line, and the last capture square must be safe by static exchange. | Audit C7 | Per item |

## The evidence engine (PRD §4.1), as built in Step 1a
- **Pin:** `Stockfish 19` with network `nn-1a298aa575a0.nnue`. `open_evidence` refuses anything else (`engine_not_pinned`).
  The binary's sha256 is recorded and is part of the config id (this Mac: `dc2f18c3…c251f`, Homebrew bottle).
- **Config:** depth 18, MultiPV 3, hash 64 MB, 1 thread, scores from White's side. The stability check runs at depth 14.
  The hash is cleared before every search, and the engine sees the position alone (no move history, which can turn a
  position into a repetition draw), so the same FEN and config always give the same answer (tested).
- **Cache:** `engine_analysis`, keyed by (FEN, config id). A config change means re-analysis, never reuse.
- **Cost measured 2026-10-13:** about 2 s per position at depth 18 (1.2 to 2.7 s over 6 middlegame positions) and 0.4 s at
  depth 14. A MISTAKE candidate needs about 4 searches (before and after the move, at both depths), so about 5 s. Step 1b will
  measure the candidate count before running everything. Several single-thread processes can run in parallel and stay
  reproducible. An on-demand sound-move check in the app costs about 2 s.

## Database rules enforced by SQLite itself (`app/db/schema.py`)
A game's pool never changes. A position takes its game's pool and never changes it, and is stored once per (game, ply, kind, mistake type, config, detector version), CLEAN included. PRACTICED only in PRACTICE, TESTED only in HELDOUT, and TESTED is final. Practice attempts only use PRACTICE positions (on insert and on update). Assessments allocate positions through `assessment_position` (the PRD's `position_ids`): only unseen, not-excluded HELDOUT positions, each **once ever**, and an answer must be for a position allocated to its assessment. At most one unsubmitted assessment per type. Assessment time is capped at 300 s. A DELAYED assessment needs its source session. A frozen `baseline_window` cannot be edited or deleted. Each rule has a test (`tests/test_db_schema.py`).

## Added in Step 1b (2026-10-13)

| # | Decision | Why | To reverse |
|---|---|---|---|
| 8 | A MISTAKE needs **at least one sound move** among the engine's top 3 lines (`sound.verified_alternatives`); otherwise it is `uncertain` (`no_sound_move`). | Found in the first trial run: a knight was lost whatever was played (even the engine's best move lost it), so it was not a "hanging piece" mistake, and as a practice position it had no right answer. No PRD number changes. | Drop `confirm` in `hanging_own_v3.py` |
| 9 | Readings in the v3 code: an M2 "equal alternative" is a top-3 line within **20 cp** of the best (`EQUAL_WITHIN_CP`; not a PRD number, the owner confirms in 1c). PRD §4.5 says the capture must be in the top line, §4.3 allows an equal alternative: §4.3 is followed. CLEAN's "attacked piece" means a knight, bishop, rook or queen (not pawns or kings), and a position where the player is in check is never CLEAN. | PRD gaps | `prd_rules.py`, `clean.py` |
| 10 | Games are imported into `game` with their pool in Step 1b (not Step 2), because a stored position needs its game's pool. The Step 2 work (pool-size check, exposure handling) is unchanged. | Order of work | n/a |

**Open for the owner (Step 1c):** in an M1 position where the player moved a piece *into* danger (`lost_piece = moved`), nothing is
wrong on the board before the move, so "What is happening here?" has no visible answer. The record stores `target_squares` (the
square the piece moved from) and `lost_piece_square_after`. Options: ask such positions differently, or keep only `lost_piece = other`
positions for recognition. The Step 1c page reports how many of each there are.

## Calibrated thresholds (PRD §4.2)
Filled in after the Step 1 hand-check. Until then the PRD defaults apply unchanged.
