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

| 11 | **Hanging piece material is net of the player's own move** (`hanging_own` v4, sound v2): counted from before the move, along the move and the refutation. A capture that is recaptured is a trade. | **Found by the owner** while answering the v1 hand-check (2026-10-15): "if I took something valuable and they take it back, I am on top". v3 counted from after the move: 38 of 190 flags were trades or small gains (4 of them on the v1 page). The sound check now also credits a move that wins material back, so 9 positions that had "no sound move" became solvable. Result: 161 M1 (73 held-out, 88 practice). | Revert to `line_swing(after_board, ...)` |
| 12 | A detector fix **retires** old rows (schema v3, `position.retired_at`) instead of deleting them: they keep their history and seen marks, and SQLite refuses to assess or practise them. A full `evidence_run` retires rows from non-current detector versions after copying seen marks to the current rows. | Deleting would forget which boards the owner saw | n/a |
| 13 | Hand-check **v1 is superseded** (it sampled v3). v2 samples the v4 store; the v1 boards stay marked as seen. | Decision 11 | n/a |

| 14 | **Recognition uses only M1 positions where the piece was left in danger** (`lost_piece = other`). Positions where the player moved the piece into danger (`lost_piece = moved`) have nothing visible to tap before the move, so they are left out of the tap-a-square step, in practice and in assessments. They stay stored. | **Owner chose (a), 2026-10-15** (the alternative was asking them differently). Enough remain: 44 held-out (16 needed) and 38 unseen in practice. | Allow `moved` with a different question |

## Calibrated thresholds (PRD §4.2): Step 1 exit gate met (2026-10-15)

**Hand-check v2** (30 practice-pool positions from `hanging_own` v4 and `missed_free` v3; scoring rule fixed before answering):
**28 of 30 real** (gate 27). M1 14/15, M2 14/15. Can't tell: 1, No: 1. Answers and per-item numbers are in
`data/evidence/handcheck_v2_result.json` (git-ignored: the owner's games).

**Thresholds: the PRD defaults are kept unchanged** (`detectors/prd_rules.py`, RULES_VERSION 1): MIN_PLY 8, DECIDED_LIMIT 600 cp,
M1 loss 200 cp, M2 loss 150 cp, MATERIAL_MIN 3, MAX_REFUTATION_PLIES 4, SOUND_MAX_LOSS 100 cp, CLEAN loss < 30 cp, plus the reading
EQUAL_WITHIN_CP 20. The gate passed at these values, and changing a number after seeing the answers would move the goalposts.

The two positions not confirmed:
- **M1, "moved into danger", B = can't tell:** the queen took a rook with check and was recaptured (net 4). The suggested safe move
  was a different capture, which made "could you have kept it safe?" hard to judge.
- **M2, A = no:** the free capture (rook takes bishop) only nets 3 after a queen trade, and the move played (a queen trade) lost
  mainly because it walked into a mating attack. **Watch item:** when most of the loss comes from something else (here, mate),
  an M2 or M1 label is correct on material but not the main lesson. A rule for that needs a new detector version and a fresh check.

Step 1 also produced decision 11 (net material), found by the owner during hand-check v1.

## Added in Step 2 (2026-10-15): pools and the baseline assessment

Built in `app/learner/assessment.py` (the service the web API and later the MCP server call), `app/api/coach.py` (thin
routes), `app/learner/realgame.py` (the frozen window), schema v5, and the web tab "My mistakes". No PRD number changed.

| # | Decision | Why | To reverse |
|---|---|---|---|
| 15 | The **baseline needs the same pool minimum as practice** (§5.2: 16 MISTAKE and 8 CLEAN held-out positions that can still be assessed, per type; CLEAN positions are shared by both types, so the count is what is left). | A baseline taken without enough positions for the three delayed tests would be wasted. | `pool_status` check in `start_baseline` |
| 16 | A move in a **CLEAN** position is sound when it is legal and loses at most `SOUND_MAX_LOSS_CP` (§4.4 rules 1 and 4; rules 2 and 3 have nothing to check there). `sound.check_clean_move`. | §4.4 is written for MISTAKE positions only | n/a |
| 17 | An assessment board shows the **position, the side to move and the legal moves only**: no last-move highlight. The type is named (cued, §7.3). | Practice hint H1 *is* "highlight the opponent's last move" (§6.3), so showing it in an unassisted test would be a hint. Legal moves are rules, not help. | Add the last move to `get_assessment` |
| 18 | **Time to decision is measured by the server**, from the first time it showed the board to the answer, capped at 300 s. A board shown again 10 s or more later (left and resumed) is flagged interrupted; a quicker repeat (a page asking twice) is not. Schema v5 `assessment_view`. | §7.4; a client clock is not trusted | `RESHOW_GAP_S` |
| 19 | **A board is assessed once, ever**, whichever of its rows (M1, M2) was allocated (schema v5 trigger). | One move can be stored as an M1 and an M2 row; seeing it once means seeing the board | n/a |
| 20 | **Random-guess rates** (§7.5): recognition = right answers ÷ (pieces + 1), per position, summed (decision 7). Move = sound legal moves ÷ legal moves, where every legal move is judged by the same sound check at the position's engine config (about 30 s a position; computed in the background from the moment a test starts and cached in `position_move_chance`). Combined = the sum of the two per-position rates multiplied (treats the two guesses as independent). | §7.5 | n/a |
| 21 | Step 2 explanations are **templates built from the evidence record** (no LLM yet; §12's LLM wording and output check come with Step 3). They name only the capture, not the rest of the engine line, which is one illustration among many, not forced. | §12: the record is the only source; separate forced from illustrative lines | n/a |
| 22 | The **frozen real-game window** (§8) is built (`realgame.freeze_baseline_window`: the last 30 games per time control before the moment, both pools, frozen once). Step 3's first practice session calls it; the rates come with Step 4. | §8 says it freezes "when the first practice session for a mistake type starts", which Step 3 builds | n/a |
| 23 | A sound check is **refused, never compared, when the engine config differs** from the position's (`engine_config_changed`). | §4.1. A second machine must run the identical Stockfish binary (see HANDOFF) | n/a |

## Added after the owner took both starting tests (2026-10-15)

The owner's two baselines showed the tap step was being used as "pick my piece": in the M2 test 3 of 5 taps, and in the M1 test all 5, were on the player's own piece, often the one then moved (and in M1 position 5 a board click silently replaced "No immediate threat"). The "spotted the problem" score therefore measured the wording, not what was seen. The move scores were sound.

| # | Decision | Why | To reverse |
|---|---|---|---|
| 24 | **Question version 2.** The tap step is a question, not a move, and the server only accepts the side it asks about: M1 the player's own pieces, M2 the opponent's (`assessment.tap_squares`; schema v6 records `assessment.question_version`). A click on the board never replaces "No immediate threat" (press the button again). The **random-guess recognition rate** counts only the tappable side: right answers ÷ (tappable pieces + 1). Assessments taken before v6 stay version 1 (either side could be tapped, rate = right ÷ (all pieces + 1)) and their results page says the tap score is not comparable. | Decision 7 counted every piece; the new rule changes the question, so it needs a new version and its own rate | `QUESTION_VERSION`, `tap_squares` |
| 25 | **A submitted baseline can be set aside** (`supersede_baseline`, `python -m app.learner.assessment supersede ID --reason ...`; schema v6 `superseded_at`, `superseded_reason`). Nothing is deleted: the answers stay, its positions stay TESTED and are never used again, and it stops being the baseline (home, start and later comparisons use the latest non-set-aside baseline). SQLite refuses to set aside an unsubmitted assessment or to undo it. | The owner retook M1 because of decision 24. Goalposts: the reason and the date are recorded, and the set-aside result stays readable | n/a |
| 26 | **The M2 starting test (question version 1) is kept** (the owner's choice with Claude's recommendation): judged by the move score only; its tap score is not comparable with later tests. Retaking would have left about 15 held-out M2 positions, under PRD §5.2's 16. | Keeps the pool for the three later tests | Set it aside later and retake if the pool allows |

## Added after the owner questioned a "nothing is wrong" position (2026-10-15)

In the retaken M1 baseline, a position labelled "No immediate threat" had a bishop attacked by a defended pawn (loses 3 for 1, net 2). The owner tapped it and moved it back. The answer "No immediate threat" was wrong, and another position in the M2 baseline had a free pawn. Decision 6 only excluded threats worth `MATERIAL_MIN` (3) or more, so small threats and free pickups passed as CLEAN. About half of the unused CLEAN positions (60 of 111 held-out) had some capture that wins something.

| # | Decision | Why | To reverse |
|---|---|---|---|
| 27 | **CLEAN v2** (`clean.VERSION` 2): a CLEAN position has no capture that wins anything for either side (`clean.NO_GAIN` = 1 point or more by static exchange, for the player's and for the opponent's captures, and for the engine's best line), and the player is not in check. It was 3 points or more. `clean.threat_reason` is the engine-free part, `clean.best_line_reason` the engine part. En passant counts (`clean.move_net`: the shared `capture_net` returns 0 for it; review on PR 70). The PRD numbers in §4.2 do not change: this is how decision 6's "no M1 or M2 opportunity" is read for CLEAN. | A fair "No immediate threat" answer needs nothing to be won at all | `NO_GAIN = R.MATERIAL_MIN`, bump `VERSION` |
| 28 | **A CLEAN position that fails the current rule is left out of the score** (`assessment.left_out_reason`): out of the scores, out of the "out of" and out of the random-guess rates. It stays on the results page with the reason ("a flaw in how this position was chosen, not in your play"). It is applied to every assessment, whichever way the answer went, and is derived when the results are read from the whole current rule: the engine-free check and the engine's best line, read from the position's own cached search (a position whose search is not cached stays in; all of the owner's were cached). Results carry `versions.clean`. This affects two positions in the owner's kept tests (M2 starting test, M1 starting test). | AGENTS rule 5: abstain rather than guess. The reason is a defect in the question, established independently of the score | Remove the `left_out` filter in `results()` |
| 29 | **The real store is rebuilt after merge** with `python -m app.learner.evidence_run run` (about 2 minutes; every engine search was cached): the v1 CLEAN rows are retired (kept, never used again), v2 rows replace them (HELDOUT 79, PRACTICE 90 on a scratch rehearsal; M1 and M2 rows unchanged). A board already assessed is never assessed again (decision 19), so flawed boards that were tested stay tested. | Detector versions are never edited in place (decision 12) | n/a |

## Added in Step 3 (2026-10-15): Replay My Mistakes

Built in `app/learner/practice.py` (the service the web API and later MCP call), routes under `/coach/practice/...`, schema v7, and the web screens (practice page, summary, practice block on the My mistakes home). Practice is always assisted (AGENTS rule 4). No PRD number changed.

| # | Decision | Why | To reverse |
|---|---|---|---|
| 30 | **The practice board does not show the opponent's last move by default**; hint H1 shows it. PRD §6.2 says to show "side to move and the last move", while §6.3 makes "highlight the opponent's last move" the first hint. Both cannot hold; H1 is kept as a real hint (same choice as decision 17 for assessments). | A hint that is already on screen is not a hint | `last_move` in `get_session`'s current block |
| 31 | **Selection:** 5 positions from the PRACTICE pool, one per game, newest game first; unseen positions first, then positions not got right on the player's own first attempt (a sound move with no hint). A repeat game is allowed only when there are not enough games, and is recorded (`repeat_games`). A session needs at least 3 positions (`MIN_SIZE`), otherwise the app says how many are left. Positions shown on an evidence page (`excluded_reason`, ADR 0006 decision 5) and M1 positions where the piece was moved into danger (decision 14) are skipped. A position becomes PRACTICED when its board is first shown, **for every practice row of that game and ply** (an M1 and an M2 row can share a board), and "got right on the player's own first attempt" is judged per board (review on PR 72). | PRD §6.1, §5.3 | `_candidates`, `MIN_SIZE` |
| 32 | **Measures** (PRD §6.3, §6.4): the highest hint level used is saved on each attempt; a retry is a new attempt and never a first attempt. *First-attempt correct* = attempt 1, sound move, no hint. *Assisted correct* = attempt 1, sound move, a hint. *Recognised* = attempt 1, right tap, no hint. The decision is the move; the tap is reported separately. The summary says plainly that practice is not a test score. | PRD §6.4 leaves "correct decision" open | `summary()` |
| 33 | **The question step keeps the "No immediate threat" button in practice**, where it is never the right answer (§6.2). | The question stays the same as in the tests, so practice does not teach "always tap something" | n/a |
| 34 | **Feedback is built only from the evidence record and the stored verdict** (template, no LLM): the original mistake, your move with SOUND / NOT SOUND and one reason, what the mistake allowed, the line on the board. The engine line is labelled "one line the engine found (not the only one)" (PRD §12: separate forced from illustrative). **The LLM wording and its output check (PRD §12) are not built yet** (task P3b); the template is the fallback that check needs anyway, and model spend is nearly at the monthly budget. | Correct by construction first; wording second | Add the LLM step in front of `_feedback`'s text |
| 35 | **Starting the first session for a type freezes the real-game baseline window** (decision 22): the last 30 games per time control before that moment, both pools, frozen once (`realgame.freeze_baseline_window`). A set-aside baseline does not unlock practice. One unfinished session per type exists at a time and resumes (SQLite index). **Starting a session (look-up, choice, window freeze, insert), creating a position's first attempt, and starting a baseline each run in one write transaction and re-check inside it**, so two simultaneous requests are serialised and the second gets the first one's result instead of a database error; a failed start freezes nothing (review on PR 72). | PRD §8, §7.1 | n/a |

Schema v7: `practice_session_position` (the positions of a session, only practice-pool mistakes that are not retired; an attempt must belong to its session's positions), `practice_attempt.recognition_correct` and `verdict_json`, `practice_session.repeat_games`, one open session per type.

## Added after the owner's first practice session (2026-10-15)

The owner's retreat Be3 saved the bishop but was marked "not sound" because the engine's best move was 1.1 pawns better (limit 1.0), and the page said "It gave away too much" (the same had happened with Be6 in a baseline test).

| # | Decision | Why | To reverse |
|---|---|---|---|
| 36 | **Wording only; the counting does not change.** When a move failed only the strict "within `SOUND_MAX_LOSS_CP` of the best move" rule, the practice feedback and the results page say what the move did: for M1 "This saves your piece, but a stronger move existed (about 1.1 pawns better)"; for M2 "This takes the free piece, but ..."; for a quiet position "A stronger move existed (...)". From `MATERIAL_MIN` (3 points, the existing constant) of loss up, the sentence does not claim the piece is safe: "This deals with the original danger, but something else went wrong: the best move was about X pawns better." Every other failure keeps its own words ("They could still win the piece."). The move still counts as not sound everywhere (scores, summary, attempts). The owner approved the wording. **A mate score is never shown as a pawn amount** (`R.MATE_CP` is a stand-in): the verdict records `mate` ("allowed": the engine's best reply is a forced mate against the mover; "missed": the mover had a forced mate), and the sentence is "... but it allows checkmate" or "... but there was a forced checkmate for you"; verdicts stored before the flag are worked out from the position's cached searches (review on PR 73). | "It gave away too much" is misleading for a piece-saving retreat; the PRD number (§4.2, 100 cp) is not mine to change | `assessment.stronger_move_words` |
