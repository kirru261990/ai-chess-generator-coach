# AI Chess Coach — Personalized Practice PRD v2

**Status:** Proposed. This version replaces v1.
**Owner:** Karthik Raman
**Date:** 2026-10-13
**Pilot:** One user (the owner). Web app plus MCP server.
**Time controls in scope:** 10-minute and 15+10 rapid games on Chess.com.
**Long-term audience:** Recreational players rated 300–1500.

---

## 0. How to use this document (for Claude Code)

1. **Run Step 0 (audit) first.** Do not write feature code before the audit is done. See section 14.
2. **Reuse what exists.** If the repo already has a board, an engine wrapper, a feedback component or a database, keep it. Change it only when this PRD requires it.
3. **Words have fixed meanings:**
   - **must** = required.
   - **should** = recommended. Deviate only with a written reason.
   - **may** = optional.
4. **Do not change a number in section 4 or section 13 without asking the owner.** The numbers are defaults. Step 1 calibrates them.
5. **The LLM never decides correctness.** Stockfish, the detectors and the rules engine decide. The LLM only words verified facts.
6. **Write tests for every acceptance criterion.** The leak tests in section 6 and section 11 are mandatory.
7. **Record each decision in `docs/decisions.md`** when the repo or the data forces a change to this PRD.

---

## 1. Goal and principle

**Goal:** Help a player recognize and avoid the mistakes they repeat in real games.

**Hypothesis:** If a player replays their own mistakes, and is then tested on unseen positions with the same mistake type, they will recognize the problem on their own and make it less often in real games.

**Core loop:**
Played game → verified mistake → replay → delayed unseen test → recurrence in later games.

**Product principle:** The coach succeeds when the player needs less coaching. It does not succeed when the player asks for more hints.

**Owner outcome (not a gate):** Raise the owner's Chess.com rapid rating from about 570 to about 724–750, checked on the owner's own games.

---

## 2. What changed from v1

| # | Change | Reason |
|---|---|---|
| 1 | A **baseline assessment** now comes before the first practice session. | Practice positions are mistakes the player already knows. Without a baseline, "improvement" cannot be measured. |
| 2 | The **held-out pool is reserved at import**, by game. A game is in the practice pool or the held-out pool. Never both. | v1 said "preferably from different games". That left the unseen pool exposed to practice. |
| 3 | v1 covers **two mistake types**: hanging piece and missed free capture. | Both are mechanically checkable. Missed opponent threats are harder to detect reliably. They move to a later phase. |
| 4 | **Numeric thresholds** now define "reliable evidence" and "sound move". | v1 left both undefined. |
| 5 | The recognition step uses **structured input** (tap a square, or "No immediate threat"). | The server can score it without an LLM. |
| 6 | Every assessment score shows its **random-guess rate**. | A 4/5 score means little if guessing gives 2 or 3. |
| 7 | **One pending assessment per mistake type.** | v1 would have created up to 7 overlapping assessments in week 1. |
| 8 | Real-game rates show **denominators**, and a floor applies before any comparison. | A few games give a meaningless rate. |
| 9 | A **hint ladder** is defined. | v1 stored hints but never put them in the flow. |
| 10 | The v1 metric "4/5 on a repeated session" is **removed**. | It measures memory of answers, not learning. |
| 11 | Every position has a **source tag**. | Lets Track 2 (in-app play) plug in later. |
| 12 | "Motif" and "category" are replaced by one term: **mistake type**. | v1 used both words for the same thing. |

---

## 3. Glossary

- **Mistake type:** One of **M1 Hanging piece** or **M2 Missed free capture**. Defined in section 4.
- **Position kind:**
  - `MISTAKE`: the position before a detected mistake.
  - `CLEAN`: a position with no immediate problem. The player moved soundly there.
  - `CURATED`: a position from outside the player's games. Later phase.
- **Pool:** `PRACTICE` or `HELDOUT`. Set on the game at import. Positions inherit it.
- **Session:** An assisted Replay practice of 5 positions.
- **Assessment:** An unassisted test of 5 unseen positions. Kind is `BASELINE` or `DELAYED`.
- **Assisted / unassisted:** Assisted means hints or feedback are available. Unassisted means neither is available. Results of the two kinds must never be mixed.
- **Sound move:** Defined in section 4.4.
- **Player:** The user who owns the Chess.com games. In the pilot, the owner.

---

## 4. Mistake detection (shared foundation)

### 4.1 Engine

- Use a **pinned Stockfish build**. Record version, network, depth, MultiPV, hash, threads and score perspective for every analysis.
- Defaults: depth ≥ 18, MultiPV = 3.
- Cache analysis by (FEN, engine config). When the engine config changes, re-analyze. Never compare results across different configs.

### 4.2 Default thresholds (configuration constants)

Step 1 calibrates these on the owner's games.

| Constant | Default | Meaning |
|---|---|---|
| `MIN_PLY` | 8 | Ignore earlier moves (opening). |
| `DECIDED_LIMIT_CP` | 600 | Skip a position when the engine already scores it beyond ±600 cp for either side. |
| `M1_EVAL_LOSS_CP` | 200 | Minimum eval loss versus the best move for an M1 mistake. |
| `M2_EVAL_LOSS_CP` | 150 | Minimum eval loss versus the best move for an M2 mistake. |
| `MATERIAL_MIN` | 3 | Minimum net material swing in points (pawn = 1, knight/bishop = 3, rook = 5, queen = 9). |
| `MAX_REFUTATION_PLIES` | 4 | The refutation must complete within this many plies. |
| `SOUND_MAX_LOSS_CP` | 100 | Maximum eval loss versus the best move for a sound move. |

### 4.3 Mistake definitions

**M1 Hanging piece.** After the player's move, the opponent can win material of at least `MATERIAL_MIN` points within `MAX_REFUTATION_PLIES`, by capturing a piece the player left capturable. This includes moving a piece to an attacked square and failing to answer a threat. The eval loss versus the best move must be at least `M1_EVAL_LOSS_CP`.

**M2 Missed free capture.** The player had a capture that wins at least `MATERIAL_MIN` points net. The player did not play it. The eval loss versus the best move must be at least `M2_EVAL_LOSS_CP`. The best move, or an equal alternative, must be that capture.

### 4.4 Sound move

A move is **sound** when all of these are true:
1. The move is legal.
2. For M1: after the move, the original refutation no longer wins `MATERIAL_MIN` points.
3. For M2: the move captures the free piece, or the eval loss versus the best move is at most `SOUND_MAX_LOSS_CP`.
4. The eval loss versus the best move is at most `SOUND_MAX_LOSS_CP`.

The server must validate any legal move the player makes. It must not accept only the engine's top move. It may pre-compute verified alternatives, and it must also evaluate any other legal move on demand with the same engine config.

### 4.5 Reliability rules (evidence must hold)

A position becomes a `MISTAKE` position only when all of these are true:
- The eval loss threshold holds at the final depth **and** at depth − 4.
- The refutation or the capture is in the engine's top line at the final depth.
- The position is not decided (`DECIDED_LIMIT_CP`).
- The original move was not the only legal move.
- The refutation completes within `MAX_REFUTATION_PLIES`.

If any check fails, **exclude the position**. Do not downgrade it.

### 4.6 Clean positions

A position is `CLEAN` when:
- The player's move was sound (eval loss under 30 cp).
- At least one piece, on either side, is attacked in the position. This prevents trivial "nothing is happening" answers.
- It passes `MIN_PLY` and `DECIDED_LIMIT_CP`.

### 4.7 Evidence record

Every `MISTAKE` position stores a structured evidence record:
`fen`, `player_move`, `best_move`, `target_squares` (the piece lost or the piece that was free), `refutation_line` (SAN and UCI), `material_swing`, `eval_before`, `eval_after`, `eval_loss`, `engine_config_id`, `detector_version`.

---

## 5. Pools and exposure

### 5.1 Pool assignment

- At import, assign each game to `PRACTICE` (60%) or `HELDOUT` (40%). Use a deterministic hash of the Chess.com game ID, stratified by time control.
- A game must never change pool.
- A position inherits the pool of its game. Therefore a practice position and a held-out position never come from the same game.

### 5.2 Minimum pool size

Before the first practice session for a mistake type, the held-out pool must hold at least **16 `MISTAKE` positions and 8 `CLEAN` positions** for that type. This covers one baseline and three delayed assessments.

If the pool is smaller, the app must show the counts and say "Not enough games yet for this mistake type". It must not lower the requirement.

### 5.3 Exposure status

Each position has one status:
- `UNSEEN`
- `PRACTICED` (practice pool only)
- `TESTED` (held-out pool only, after the assessment is submitted)

Rules:
- Held-out positions must be returned **only** by the assessment endpoints.
- Practice sessions, hints and feedback must never use a held-out position.
- A `TESTED` position must never be reused in a later assessment.

---

## 6. Feature A — Replay My Mistakes (assisted practice)

**User story:** As a player, I want to revisit positions where I made a mistake, so I can recognize what I missed and make a better decision.

### 6.1 Position selection

- The player chooses a mistake type. The default is the type with the most unpracticed `MISTAKE` positions.
- The session uses 5 positions from the `PRACTICE` pool.
- Positions must come from different games. If fewer than 5 games are available, allow repeat games and record that fact.
- Order: newest game first.
- Positions the player got wrong on the first attempt may appear again in a later session.
- The practice pool for a type is **locked until the baseline assessment for that type is complete** (section 7.1).

### 6.2 Practice flow (per position)

1. **Show the board** immediately before the player's original mistake. Show side to move and the last move. Show nothing else. No eval bar, no best move, no arrows, no move classification.
2. **Recognition:** Ask "What is happening here?" The player taps one square (a piece) or taps "No immediate threat".
   - Recognition is correct when the tapped square is in `target_squares`.
   - In practice, the answer is never "No immediate threat" (all practice positions are `MISTAKE`).
3. **Move:** The player makes a legal move. The server validates it.
4. **Feedback.** Show:
   - The original mistake.
   - The player's new move, with a SOUND or NOT SOUND verdict from section 4.4.
   - What the original mistake allowed (the refutation line, shown on the board).
   - Whether the new move avoids that problem.
5. **Next:** The player picks **Retry** or **Next position**. A retry resets the position. A retry never counts as a first attempt.

### 6.3 Hint ladder (practice only)

| Level | Hint |
|---|---|
| H1 | Highlight the opponent's last move. |
| H2 | Highlight the piece at risk (M1) or the capturable piece (M2). |
| H3 | Show the refutation line (M1) or the capturing move (M2). |

- The server records the highest hint level used for each attempt.
- An attempt with hint level ≥ 1 does **not** count as "first-attempt correct". It counts as "assisted correct".

### 6.4 Session summary

Show:
- Positions completed (of 5).
- First-attempt correct decisions (no hints).
- Assisted-correct decisions.
- Positions that needed a retry.
- Mistake patterns the player recognized correctly.

### 6.5 Acceptance criteria

- A complete five-position session works end to end.
- **Leak test:** Before the first attempt on a position, no API response contains the best move, the engine eval, the refutation line or the target squares. The test must fail the build if any of them leaks.
- The server validates every move with the chess rules.
- Every NOT SOUND move gets a specific explanation backed by the evidence record (section 12).
- Every attempt and its source game and ply are saved.
- An interrupted session resumes at the same position, with the same hint state.

---

## 7. Feature B — Did I Actually Learn? (unassisted assessment)

**User story:** As a player, I want to test whether I can recognize the same kind of mistake in unfamiliar positions, without help.

### 7.1 Baseline assessment

- Before the first practice session for a mistake type, the player must complete a `BASELINE` assessment for that type.
- It uses 5 `HELDOUT` positions with the same composition and rules as a delayed assessment (7.3, 7.4).

### 7.2 Delayed assessment

- A completed session creates a `DELAYED` assessment for its mistake type **only if no assessment for that type is pending**.
- The assessment becomes available **72 hours** after the session's completion time.
- It does not expire.
- When the player submits it, the next completed session may create the next one. This sets a cadence of at least 3 days.
- Target: 3 delayed assessments per mistake type in the pilot.

### 7.3 Composition

- 5 `HELDOUT` positions: **3–4 `MISTAKE` and 1–2 `CLEAN`**.
- The assessment names the mistake type to the player ("cued").
- The assessment must never show a position's kind or answer.
- The position order is random.

### 7.4 Assessment flow

- No hints, no eval bar, no move classification, no feedback.
- For each position, the server records: recognition response, chosen move, recognition correct, move sound, time to decision.
- Time to decision is capped at 300 s. A position that was interrupted must be flagged.
- A submitted position cannot be revisited.
- The app reveals answers and explanations **only after all 5 positions are submitted**.
- An interrupted assessment resumes at the first unsubmitted position.

### 7.5 Scoring

- A position is **correct** when recognition is correct **and** the move is sound.
  - For `CLEAN`: recognition is correct only for "No immediate threat".
- Report three numbers: recognition accuracy, move accuracy, combined accuracy.
- Equivalent sound moves count equally (section 4.4).
- Report the **random-guess expectation** next to every score:
  - Move chance = sound legal moves ÷ all legal moves, per position, summed over the assessment.
  - Recognition chance = 1 ÷ (number of pieces on the board + 1), per position, summed.

### 7.6 Learning comparison (Progress screen)

Compare, per mistake type:
- Baseline accuracy versus each delayed accuracy.
- First-attempt accuracy in practice (assisted, shown separately).
- Decision time.
- Hint dependence in practice (share of attempts with hint level ≥ 1).
- Recurring mistake categories.

Assisted practice results must never appear inside an unassisted score.

### 7.7 Acceptance criteria

- A baseline assessment is required before practice. The app blocks practice until it is done.
- A delayed assessment becomes available exactly 72 hours after the session that created it.
- No `TESTED` or `PRACTICED` position appears in any assessment.
- No hint or feedback exists in any assessment screen. A test must verify this.
- Results persist across sessions.
- The player can view practice versus assessment outcomes.

---

## 8. Real-game tracking

**Sync:** Manual "Sync games" button, plus a sync at app start.

**Frozen baseline:** When the first practice session for a mistake type starts, freeze the baseline window: the **last 30 games per time control** before that moment. Never change it.

**Post window:** All games played after the freeze, per time control.

**Rates** (same detectors and engine config for both windows):
- **M1 rate:** M1 mistakes per 100 player moves (from `MIN_PLY`).
- **M2 rate:** missed free captures ÷ free captures available.

**Reporting rules:**
- Separate results by time control.
- Always show the denominators: games, moves or opportunities, and events.
- Show a before/after comparison only when each window has **at least 20 games** (M1) or **at least 20 opportunities** (M2). Otherwise show "Not enough data yet".
- Label results "directional evidence, not proof of cause".
- When the engine config changes, re-analyze the baseline window too.

---

## 9. Screens

| Screen | Purpose |
|---|---|
| Home | Choose a mistake type. Shows pool counts, the baseline status, the next assessment due date. |
| Baseline / Delayed Assessment | 5 unseen decisions. No assistance. |
| Practice Board | Identify the problem → choose a move → review the consequence. Hint button. |
| Session Summary | What was learned and what needs more practice. |
| Assessment Results | Shown after final submit. Answers, explanations, score, random-guess rate. |
| Progress | Baseline vs delayed accuracy, practice accuracy, real-game rates with denominators. |

Reuse the existing board, feedback and hint components where possible.

---

## 10. Data model

Use the repo's existing database. If none exists, use SQLite. In-memory state is not enough. Persist only what is needed.

- `game`: id, source (`chesscom`), platform_id, time_control, played_at, pool, pgn, analyzed_with_config_id
- `engine_config`: id, version, network, depth, multipv, hash, threads, score_perspective
- `position`: id, game_id (nullable), ply, fen, kind, mistake_type, source_tag, pool, original_move, evidence_json, verified_alternatives, exposure_status, engine_config_id, detector_version
- `practice_session`: id, user, mistake_type, status (`created`, `in_progress`, `completed`, `abandoned`), started_at, completed_at
- `practice_attempt`: id, session_id, position_id, attempt_number, recognition_response, move, move_sound, hint_level, elapsed_ms
- `assessment`: id, user, mistake_type, kind (`BASELINE`, `DELAYED`), source_session_id, due_at, status, position_ids, submitted_at
- `assessment_result`: id, assessment_id, position_id, recognition_response, recognition_correct, move, move_sound, elapsed_ms, interrupted
- `baseline_window`: id, user, mistake_type, time_control, game_ids, frozen_at
- `realgame_stat`: window, time_control, mistake_type, games, moves_or_opportunities, events, engine_config_id

**Rules**
- The server owns legal moves, position validation, scoring and pool allocation.
- Assessment allocations must be durable.
- A position's `pool` and `exposure_status` must never be set by a client.
- Personal pilot only: reuse the existing identity and configuration. Defer multi-user accounts.

---

## 11. Server and MCP surface

The web app and the MCP server must call the **same service layer**. Neither one may contain its own scoring logic.

**Operations** (names are suggestions):
`get_home`, `start_baseline`, `start_session`, `submit_recognition`, `submit_move`, `get_hint`, `get_session_summary`, `get_assessment`, `submit_assessment_item`, `submit_assessment`, `get_progress`, `sync_games`.

**Rules**
- Practice endpoints must never return a `HELDOUT` position.
- Assessment endpoints must never return a hint, an eval or feedback before final submit.
- A response before the first attempt must not contain `best_move`, `eval`, `refutation_line` or `target_squares`.
- Add automated tests for each rule.

---

## 12. Explanation rules

- The **evidence record** (section 4.7) is the only source for explanations.
- The LLM receives the evidence record and writes a short explanation in plain language. It must not add a chess claim that is not in the record.
- **Output check:** Parse every move or square the LLM names. Reject the explanation if any move or square is not in the evidence record. Fall back to a template explanation built directly from the record.
- Show the short explanation first. Show the board line on request.
- Separate forced lines from illustrative lines in the wording.

---

## 13. Metrics and decision gate

| Metric | Initial pilot target | Notes |
|---|---|---|
| Practice completion | 5/5 positions per session | Operational. Assisted. |
| Unseen accuracy (delayed) | At least 4/5, and at least 2 positions above the random-guess expectation | Unassisted. Combined accuracy. |
| Gain over baseline | Mean delayed accuracy exceeds baseline accuracy by at least 1 position of 5 | Unassisted. |
| Retention | Improvement across 3 delayed assessments | Per mistake type. |
| Real-game transfer | Directional reduction in the same mistake rate | Only when the floors in section 8 are met. |

These are pilot thresholds. They are not learning benchmarks. Report every denominator. A five-position result is not statistically conclusive. The owner is both builder and user, so treat the results as a usefulness check, not evidence of effectiveness.

**Decision gate (after weeks 1–3):**
- Week 1: baseline for both mistake types, then daily sessions.
- Weeks 2–3: delayed assessments as they become due. Review new real games for the same mistakes.
- **Continue investing** if the sessions are useful, performance on unseen positions beats baseline and chance, and real-game evidence is directionally encouraging.

---

## 14. Build sequence

Each step has an exit gate. Do not start the next step before the gate is met.

### Step 0 — Audit (1–2 days)
- Compare the repo against this PRD.
- Write `docs/audit.md`: what exists, what is missing, what conflicts, which database and which engine wrapper exist.
- **Exit:** The owner reviews the audit and approves the plan.

### Step 1 — Evidence layer
- Chess.com import for 10-min and 15+10 rapid games.
- Pinned Stockfish with recorded configs and a cache.
- M1 and M2 detectors, the sound-move validator, the `CLEAN` selector, evidence records.
- **Exit:** The owner hand-checks 30 flagged positions. At least 27 must be real mistakes. Thresholds are calibrated and recorded in `docs/decisions.md`.

### Step 2 — Pools and baseline
- Pool assignment, exposure status, pool size check.
- Baseline assessment flow and scoring, including random-guess rates.
- Frozen real-game baseline window.
- **Exit:** A baseline assessment works end to end. A test proves held-out positions never leave the assessment endpoints.

### Step 3 — Replay My Mistakes (Feature A)
- Five-position sessions, tap-to-select recognition, move validation, hint ladder, feedback with the output check, summary, resume.
- **Exit:** One full session works. The leak test passes. An interrupted session resumes.

### Step 4 — Did I Actually Learn? (Feature B) and Progress
- Delayed assessment scheduling (72 hours, one pending per type), results reveal, Progress screen, real-game tracking with floors.
- **Exit:** A delayed assessment appears after 72 hours and shows no previously seen position. The Progress screen shows practice versus assessment outcomes.

### Step 5 — MCP server (later)
- Expose the operations in section 11 as MCP tools on the same service layer.

### Step 6 — Friends (3–4 weeks after launch)
- Multi-user accounts. A spaced-repetition review scheduler (FSRS or similar) as a training aid. It must stay separate from assessment.

### Step 7 — Track 2: in-app play (later)
- Players with few Chess.com games build their own mistake history by playing on the app.
- Tag every position with its source: Chess.com game, in-app game, or curated. Keep time controls and opponent types separate.
- Play games against a bot produce different mistakes than games against humans. Do not mix their rates.
- Do not count hint-assisted or practice-flow games in the unassisted real-game rate.

---

## 15. Out of scope for v1

- New AI personalities or chat interfaces.
- Ratings, streaks, leaderboards or gamification.
- Opening memorization.
- Adaptive ML difficulty models.
- Forks, missed opponent threats and other advanced tactics.
- Multi-user support.
- A mobile-native app.
- Lichess import.
- A spaced-repetition scheduler.
- In-app play (Track 2).

The data model must not block any of these later.

---

## 16. Risks and assumptions

- **Detector precision.** Wrong flags destroy trust. Step 1 gates this at 27 of 30.
- **Pool size.** A player with few games lacks enough positions. The app must show counts and block. The owner is assumed to have enough rapid games.
- **Small samples.** Five positions per assessment is noisy. The PRD reports random-guess rates and avoids causal claims.
- **Cued tests.** An assessment names its mistake type, which helps the player. Real-game rates are the uncued check.
- **Owner as subject.** The owner knows how the detectors work. Treat results as a usefulness check.
- **Engine changes.** A new Stockfish version changes results. Re-analyze the baseline before you compare.
- **Assumption:** The Chess.com username comes from existing configuration.

---

## 17. Open items

- Calibrate every threshold in section 4.2 in Step 1.
- Confirm the database and engine wrapper in Step 0.
- Decide whether the assessment cue (naming the mistake type) stays or becomes an uncued mixed assessment in a later version.
