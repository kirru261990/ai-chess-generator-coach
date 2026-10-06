# real_play_v1: label rule (v0.4, decisions made, set not yet frozen)

**Status:** the owner delegated the open decisions on 2026-10-05 and asked that each be
reversible; they are in section 12 with reasons and how to undo them. **No detector has been run
on any position of this set, and no position has been chosen yet.** This file freezes at the
freeze step (section 8): it is hashed and never edited afterwards. A flaw found later means a new
set version, never an edit.

**Purpose:** measure how accurately `hanging_own` and `missed_free` classify moves on
positions from real play, including cases built to break them, without the labels depending on
the detectors or on a rule that was adjusted after seeing their output. The two earlier draft
sets (`hanging_own_v1`, `missed_free_v1`) failed on both counts, as their READMEs say.

**What this set can and cannot show.** It measures *detection accuracy* (when a move hangs a
piece or ignores a free one, does the detector say so, and does it stay quiet otherwise?). It
does **not** measure how often these mistakes happen in your games or anyone's: puzzle positions
are curated tactics, so opportunities are far denser than in normal play.

**Changes in v0.3** (after GPT's first review of PR #21; all three comments were reproduced):
1. "No opportunity" is now defined by a **material check over every legal capture**, not by the
   engine's preferred move. An engine can prefer another move (for example because a capture allows mate)
   while a capture still legally wins material; such a position is not `not_applicable`.
2. Every real item is now **also confirmed by an independent exchange search** in the builder, not only
   by Lichess's theme and solution.
3. The theme exclusions now apply to **every** sampler (the negatives skipped them before).
4. The hand-check questions were rewritten so the answers map to **all four labels** (section 9).

**Changes in v0.4** (after GPT's second pair of comments on PR #21; both reproduced):
1. `hanging_own` real items now require the **safe-versus-hanging choice** their label assumes. A blunder
   needs at least one safe alternative; a "safe" move needs at least one alternative that would have hung
   something. Otherwise the correct outcome is `not_applicable`, not `missed` or `taken` (found: 12 blunders
   with no safe alternative, 2 safe items where nothing could hang).
2. Real blunders are labelled by the **same evidence rule as the detectors**: `missed` if the engine loss is
   at least 300 cp, `uncertain` if it is under 100 cp (the move hangs material but the engine does not
   confirm a loss, for example when mate is coming anyway), excluded if 100-299 cp. The engine numbers are
   stored on every such item (`engine_best_cp`, `engine_after_cp`, `loss_cp`). Hand-built adversarial items
   record the same numbers and the builder asserts they agree with the label.
3. Each item has a `label` (the outcome a correct detector gives **with** engine evidence) and a
   `material_label` (what the board alone shows). They differ only when the engine overrides the material
   picture. **The hand-check validates `material_label`**; the engine part of a label is verified by the
   stored numbers, which people cannot judge.

---

## 1. Definitions

- A **free piece** is a non-pawn, non-king piece that the side to move can win by a *legal*
  capture that gains at least 2 pawns of material after best recaptures, with every capture and
  recapture legal (pins and checks respected). Pawns, kings, en passant and promotion gains are
  out of scope, as in the detectors.
- A move **hangs a piece** if, after it, the opponent has such a capture of one of the mover's
  non-pawn pieces.
- Detector outcomes are `taken | missed | uncertain | not_applicable`. The labels below are the
  outcome a correct detector should give **when it has engine evidence**; the static-only run
  is scored against the same labels and reported separately.

## 2. Sources, and why each is independent of the detectors

| Source | Used for | Independence |
|---|---|---|
| **Lichess puzzle database** (CC0; file `lichess_db_puzzle.csv.zst`, sha256 `76335bfa7d7c4a7f93c1366d81549e53951ebb79dd43d34904cab8f22d962f8d`, downloaded 2026-10-05) | real positives and real safe moves | Puzzle themes and solutions were produced by Lichess's own generator and engine checks, not by our code. |
| **Stockfish at depth 14** (version recorded) | confirming constructed "ignored it" moves only | Search results, not our static exchange. |
| **Independent exchange search** (in the builder) | confirming every real item; defining "no opportunity"; cross-checking the hand-built labels | A full search over every legal capture and recapture in any order, written separately from the detectors' cheapest-attacker-first code, using only `python-chess`. Agreement with the detectors is then evidence, not an echo. |
| **Hand-built adversarial positions** | pins, losing captures, several capturers, pinned defenders | Labelled by construction with a written reason for each; every one hand-checked. |

The builder script must import **nothing** from `app/detectors/`. It may use `python-chess`,
`app/engine/stockfish.py` (to run the engine), one ranking helper from the review module, and the puzzle
file. A test enforces the import rule.

## 3. Reading the puzzle format

For each puzzle row: `FEN` is the position **before the opponent's last move**; `Moves[0]` is
that move (a real human move that gave the solver a chance); `Moves[1]` is the solver's first
move, then the line alternates. Only puzzles tagged `hangingPiece`, rated 400 to 1199, with no
excluded theme (section 6) are eligible. Deduplicate by `PuzzleId`.

## 4. Labels

### 4a. `missed_free`

| Label | Item `(position, move played)` | How the label is decided |
|---|---|---|
| `taken` | position after `Moves[0]`; move = `Moves[1]` | Eligible if `Moves[1]` captures a non-pawn piece **and** the independent exchange search confirms that capture itself nets at least 2 pawns after the opponent's best recaptures. The puzzle's own solution is the proof that taking it is right. |
| `missed` (constructed) | a position from a *different* puzzle in the pool (so it is independent of the `taken` items); move = a random legal, non-capturing move | Kept only if the independent exchange search confirms an opportunity exists, Stockfish (depth 14) says its best move is the puzzle's capture, and that move is worse than the best move by **at least 300 cp**. Up to 6 random moves are tried per puzzle. Marked `constructed`: it is not real behaviour. |
| `not_applicable` | real positions from puzzles *not* tagged `hangingPiece`, same exclusions | Kept only if **no legal capture of a non-pawn piece nets at least 2 pawns** by the independent exchange search, although the mover has a capture of a defended non-pawn piece (a hard negative). The engine is not used. |
| any | adversarial positions (section 5) | By construction. |

### 4b. `hanging_own`

| Label | Item | How the label is decided |
|---|---|---|
| `missed` (real) | position = `FEN`; move = `Moves[0]` | Eligible if `Moves[1]` captures a **non-pawn piece belonging to the side that played `Moves[0]`** **and** the independent exchange search confirms that, after `Moves[0]`, the opponent can win at least 2 pawns by capturing one of that side's non-pawn pieces, **and** the mover had at least one safe alternative. The label is then set by the engine evidence: `missed` if the loss is at least 300 cp, `uncertain` if under 100 cp, excluded if in between. Real human moves that hung a piece. |
| `taken` (real, safe) | position after `Moves[0]`; move = `Moves[1]` | A solver move Lichess verified as best. Eligible only if the puzzle has none of the sacrifice-type themes (section 6) **and** the independent exchange search confirms that, after the move, the opponent cannot win 2 pawns by capturing one of the mover's non-pawn pieces, **and** some other legal move would have hung a piece (so there was a real choice). |
| `not_applicable` | adversarial positions only | Positions where no move can hang a piece, or where every move does. |
| any | adversarial positions (section 5) | By construction. |

## 5. Adversarial positions (hand-built, about 10 per detector in v1)

Each carries a one-line written reason, and **all are hand-checked**:

1. A capturer pinned to its king, so the capture is illegal.
2. A defender pinned to its king, so the recapture is illegal (piece really is free).
3. A defender that looks pinned but is not (pin along the wrong line).
4. A capture that loses material (queen takes a defended rook).
5. Several capturers of different values on one target (cheapest legal one decides).
6. A capture that is illegal because the mover's king is in check.
7. A piece attacked only by a pawn that can capture it, but only into a loss of the pawn's own protection.
8. Mate beats the free piece (the detector should say `uncertain` with evidence).

## 6. Exclusions (decided now, applied before any detector runs)

Puzzles with a **deliberate-sacrifice theme** are excluded **from every sampler, including the negatives**, because a move that is meant to give
material makes "hanging" ambiguous: `sacrifice`, `attraction`, `deflection`, `intermezzo`,
`quietMove`, `clearance`, `zugzwang`. Also excluded: positions where `Moves[1]` is a promotion or
en passant capture, and any position that is not valid and reachable when replayed with
`python-chess`.

**Mate and pin themes are kept.** An earlier draft excluded all mate themes; the feasibility
count (section 7) showed that removed 64% of puzzles and left the 400-599 band with 373. Instead,
each item carries a `mate_theme` tag, and results are reported **with and without** mate-theme
items, so a mate that competes with a free piece cannot hide inside a headline number.

## 7. Sample sizes and sampling

Seeded and reproducible; the seed is recorded in the builder and in the set README.

| Stratum | Target |
|---|---|
| `missed_free` `taken` (real), 10 per rating band: 400-599, 600-799, 800-999, 1000-1199 | 40 |
| `missed_free` `missed` (constructed), from other puzzles | 40 |
| `missed_free` `not_applicable` (engine-derived) | 20 |
| `hanging_own` `missed` (real), 10 per band | 40 |
| `hanging_own` `taken` (real, safe), 10 per band | 40 |
| Adversarial, per detector | 10 |

**The two detectors draw on the same puzzles** (a solver's capture always takes a piece of the
side that blundered), so the sampler draws **disjoint** puzzle sets for the two detectors; no
puzzle supports both.

About 90 labelled items per detector. At that size a precision or recall figure carries a wide
interval, so **every figure is reported with its denominator and a 95% Wilson interval**, per
stratum and overall. If a stratum cannot be filled, the shortfall is reported, not hidden.

### Feasibility check (counts only; nothing was selected and no detector was run)

Counted on 5 Oct 2026 using only `python-chess` and the puzzle file. 91,511 puzzles are tagged
`hangingPiece` with rating 400 to 1199 (after de-duplication), all valid.

- **First draft (all mate themes excluded):** 58,724 (64%) removed, leaving 32,774 eligible, with
  only **373** in the 400-599 band. Rejected for that reason.
- **Current rule (sacrifice-type themes only):** 2,201 removed, leaving **89,214 eligible** (first
  solver move captures a non-pawn piece), spread evenly enough for 10 per band:

| Rating band | Eligible puzzles | Of which carry a mate theme |
|---|---|---|
| 400-599 | 15,095 | 14,722 |
| 600-799 | 19,585 | 16,677 |
| 800-999 | 27,918 | 16,165 |
| 1000-1199 | 26,616 | 8,876 |

63% of eligible puzzles carry a mate theme, so the `mate_theme` tag matters. The two detectors
draw on this same pool, so the sampler uses disjoint puzzles for each stratum.

## 8. Freezing procedure (the order matters)

1. The owner approves this file (a commit on `main`).
2. The builder script is written and committed. It produces `positions.jsonl` with the labels
   and the recorded provenance: engine version and depth, seed, puzzle file hash.
3. **Hand-check** (section 9) happens now, before any detector sees the set.
4. If hand-checking changes any label or the rule, bump to `real_play_v2` (new sample); do not
   edit v1.
5. Freeze: commit `positions.jsonl`, record the sha256 of this file and of `positions.jsonl` in
   `HANDOFF.md`, and list the set under "Frozen eval sets".
6. Only then run the detectors, record each detector's version, and publish the numbers in
   `evals/reports/` with the denominators.

If a later problem with the rule or labels is found, the published numbers stay, with a note
explaining the problem, and a new set version is built. The set is never tuned toward the
detectors, and the detectors are never tuned toward this set's results before the report is
written.

## 9. Hand-check protocol (about 30 labels, plain yes/no questions)

The checker answers questions about the board, not "is this label right?". Each sheet row gives
the FEN, the move, a Lichess analysis-board link, and three questions **without the proposed
label**. The questions are in the sheets (`handcheck_*.md`); their answers map to the labels as
follows.

**`missed_free`** (A: could the side to move win material by a capture worth at least 2 pawns? B: does
the move shown make such a capture? C: does something matter more than the material, such as mate?)

| A | B | C | Label implied |
|---|---|---|---|
| no | any | any | `not_applicable` |
| yes | yes | any | `taken` |
| yes | no | no | `missed` |
| yes | no | yes | `uncertain` |

**`hanging_own`** (A: after the move, can the opponent win at least 2 pawns by capturing a non-pawn
piece? B, if A is yes: could the mover have avoided it with another legal move? C, if A is no: could any
legal move have left a piece to be won?)

| A | B | C | Label implied |
|---|---|---|---|
| yes | yes | n/a | `missed` |
| yes | no | n/a | `not_applicable` (every move hangs something) |
| no | n/a | yes | `taken` |
| no | n/a | no | `not_applicable` (nothing could hang) |

- **What the answers are compared with:** each item's `material_label`, not its `label`. A few real blunders are `uncertain` in `label` because the engine does not confirm a loss; the checkers answer only about material, and their answers map to `missed` for those.
- **The owner uses a simpler page** (`handcheck_owner.html`, built by `evals/tools/make_handcheck_page.py`): the board with the
  move drawn as an arrow, the move in plain words, and at most two yes / no / can't tell questions per item. Its
  answers map to labels like this (the checkmate question is left out because none of the owner's items depends on it):
  `missed_free`: A no is `not_applicable`; A yes and B yes is `taken`; A yes and B no is `missed`. `hanging_own`: A yes is
  `missed`; A no is `taken` (every `real_safe` item has an alternative that would have hung something, by construction).
  The full three-question sheet (`handcheck_second.md`) is for the second reviewer.
- **Two checkers, independently:** the owner (30 items) and a second reviewer such as GPT following
  `REVIEW.md` (a different 30, plus all adversarial items). A question the owner cannot answer is marked
  `can't tell`; it is not forced.
- **Sample (seeded):** about 8 real `taken`, 8 `missed` (4 real, 4 constructed), 4 `not_applicable`, and the
  adversarial items.
- **Pass rule:** at most 10% of answered items give a different implied label (3 of 30), and no pattern
  in the disagreements. Otherwise the rule is revised and the set rebuilt as v2 (step 4 of section 8).
  `can't tell` items are replaced, not counted as agreement.
- Record the counts, the date and who checked in the set README. "Human-reviewed" may be claimed only for the
  items actually reviewed, and only by whom.

## 10. What is reported

For each detector version, static-only and with engine evidence:

- Precision and recall for `missed`, with denominators and 95% Wilson intervals
- The full confusion matrix (including `uncertain` and `not_applicable`)
- Results per stratum and per rating band, **separately for real and constructed items**, and with and without mate-theme items
- Every disagreement, listed, with a failure category (not just a count)

Claims must separate: what the detectors do on curated puzzle positions, what they do on
constructed positions, and what is still unknown about real games. No figure from this set is
described as a rate of mistakes in anyone's play.

## 11. Known weaknesses of this design (stated up front)

1. Puzzle positions are curated tactics. Opportunities are dense, so recall here overstates
   recall on ordinary positions, and precision on ordinary positions is untested.
2. Constructed `missed` items are not real behaviour, and the engine confirmation reuses the
   same engine that produces the evidence the detectors can use. Static-only results avoid
   that overlap, so both are reported.
3. Puzzles show only correct solutions, so there are no real examples of a player *ignoring* a
   free piece. A real-games sample (Lichess games or your own after the baseline freeze) would fix
   this; it is not part of v1.
4. Lichess themes come from Lichess's generator, not from people. Their error rate is unknown;
   the hand-check is the only human check.
5. Lichess puzzle ratings are on Lichess's scale, and Lichess players are not a sample of
   all players under 1000.
6. About 100 items per detector gives wide intervals. Small differences between detector versions
   will not be distinguishable.

## 12. Decisions made (owner delegated on 2026-10-05; each is reversible)

| # | Decision | Why | How to reverse |
|---|---|---|---|
| 1 | **Keep constructed `missed` items**, marked `constructed`, reported separately | Puzzles only show correct solutions, so without them there are no `missed` examples to measure recall on | Drop items with `constructed=true` in the analysis. No rebuild needed |
| 2 | **300 cp** loss threshold, **depth 14** | About a piece's worth: clearly an error, not noise; depth 14 is stronger than the earlier sets' 12 and cheap for ~100 items | Parameters are recorded per item; change them and build v2 |
| 3 | **About 90 items per detector**, 10 adversarial each | Enough to see gross failures with honest wide intervals, small enough to hand-check | Add a v2 with a new seed; v1 stays |
| 4 | **Keep mate themes, tag them**, report with and without; exclude only sacrifice-type themes | Excluding mates left the 400-599 band with 373 puzzles and tilted the set toward harder ones | Filter on `mate_theme` in the analysis |
| 5 | **Hand-check by yes/no board questions**, owner plus a second reviewer, labels hidden | The owner said they could not judge chess labels directly; concrete yes/no questions about the board are answerable and avoid anchoring on our label | Add or swap reviewers; the sheet is regenerable |
| 8 | **"No opportunity" is defined by the material search, not the engine's choice** | An engine can prefer another move while a capture still legally wins material (found in review) | Add the engine condition back as an extra filter and rebuild as v2 |
| 6 | **No real-games sample in v1**; a bounded one is a v2 option | The games files are about 28 GB a month and need a streaming plan and fresh approval | v2 |
| 9 | Real blunders use the **same evidence thresholds as the detectors' labels**: 300 cp for `missed`, under 100 cp for `uncertain`, excluded between | The label is an outcome with engine evidence; material alone overstated 8 of 40 (found in review) | Change the thresholds and build v2; the engine numbers are stored per item |
| 7 | Constructed-miss and `taken` items come from **different puzzles** | Keeps items independent | Seeded sampler option |

Open for later, not blocking: the licence choice (T24) and the real-games sample (decision 6).
