# real_play_v1: label rule (DRAFT v0.1, not frozen)

**Status:** draft for the owner's review. **No detector has been run on any position of this
set, and no position has been chosen yet.** Once approved, this file is frozen (see section 8):
it is committed, hashed, and never edited. A flaw found later means a new set version, never an
edit.

**Purpose:** measure how accurately `hanging_own` and `missed_free` classify moves on
positions from real play, including cases built to break them, without the labels depending on
the detectors or on a rule that was adjusted after seeing their output. The two earlier draft
sets (`hanging_own_v1`, `missed_free_v1`) failed on both counts, as their READMEs say.

**What this set can and cannot show.** It measures *detection accuracy* (when a move hangs a
piece or ignores a free one, does the detector say so, and does it stay quiet otherwise?). It
does **not** measure how often these mistakes happen in your games or anyone's: puzzle positions
are curated tactics, so opportunities are far denser than in normal play.

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
| **Stockfish at fixed depth** (version and depth recorded) | confirming constructed "ignored it" moves; confirming "no opportunity" positions | Search results, not our static exchange. |
| **Hand-built adversarial positions** | pins, losing captures, several capturers, pinned defenders | Labelled by construction with a written reason for each; every one hand-checked. |

The builder script must import **nothing** from `app/detectors/`. It may use `python-chess`,
`app/engine/stockfish.py` (to run the engine) and the puzzle file.

## 3. Reading the puzzle format

For each puzzle row: `FEN` is the position **before the opponent's last move**; `Moves[0]` is
that move (a real human move that gave the solver a chance); `Moves[1]` is the solver's first
move, then the line alternates. Only puzzles tagged `hangingPiece`, rated 400 to 1199, with no
excluded theme (section 6) are eligible. Deduplicate by `PuzzleId`.

## 4. Labels

### 4a. `missed_free`

| Label | Item `(position, move played)` | How the label is decided |
|---|---|---|
| `taken` | position after `Moves[0]`; move = `Moves[1]` | Eligible if `Moves[1]` captures a non-pawn piece. The puzzle's own solution is the proof that taking it is right. |
| `missed` (constructed) | the same position; move = a different legal, non-capturing move | Kept only if Stockfish (depth D) says that move is worse than the best move by **at least 300 cp** and the best move is the puzzle's capture. Marked `constructed`: it is not real behaviour. |
| `not_applicable` | engine-derived hard negatives (below) | Kept only if Stockfish's best move is **not** a capture that wins at least 2 pawns along its line (6 plies), although the mover has a capture of a defended non-pawn piece. |
| any | adversarial positions (section 5) | By construction. |

### 4b. `hanging_own`

| Label | Item | How the label is decided |
|---|---|---|
| `missed` (real) | position = `FEN`; move = `Moves[0]` | Eligible if `Moves[1]` captures a **non-pawn piece belonging to the side that played `Moves[0]`**. Real human blunders that hung a piece. |
| `taken` (real, safe) | position after `Moves[0]`; move = `Moves[1]` | A solver move Lichess verified as best. Eligible only if the puzzle has none of the sacrifice-type themes (section 6), so a deliberate sacrifice is never labelled a mistake or a safe move by accident. |
| `not_applicable` | adversarial positions only | Positions where no move can hang a piece, or where every move does. |
| any | adversarial positions (section 5) | By construction. |

## 5. Adversarial positions (hand-built, about 20 per detector)

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

Puzzles with any of these themes are excluded, because a deliberate sacrifice or a mate makes
"free piece" or "hanging" ambiguous: `sacrifice`, `attraction`, `deflection`, `intermezzo`,
`quietMove`, `clearance`, `zugzwang`, `mate`, `mateIn1` to `mateIn5`, `anastasiaMate`,
`arabianMate`, `backRankMate`, `bodenMate`, `doubleBishopMate`, `dovetailMate`,
`hookMate`, `smotheredMate`, `killBoxMate`, `vukovicMate`, `cornerMate`.
Also excluded: positions where `Moves[1]` is a promotion or en passant capture, and any
position that is not a valid, reachable chess position when replayed with `python-chess`.

(The `pin`, `fork`, `skewer` and `discoveredAttack` themes are **kept**: they supply the
pin-related positions we need.)

## 7. Sample sizes and sampling

Seeded and reproducible; the seed is recorded in the builder and in the set README.

| Stratum | Target |
|---|---|
| `missed_free` `taken` (real), 10 per rating band: 400-599, 600-799, 800-999, 1000-1199 | 40 |
| `missed_free` `missed` (constructed), same positions where an eligible move exists | 40 |
| `missed_free` `not_applicable` (engine-derived) | 20 |
| `hanging_own` `missed` (real), 10 per band | 40 |
| `hanging_own` `taken` (real, safe), 10 per band | 40 |
| Adversarial, per detector | 20 |

**The two detectors draw on the same puzzles** (a solver's capture always takes a piece of the
side that blundered), so the sampler draws **disjoint** puzzle sets for the two detectors; no
puzzle supports both.

About 100 labelled items per detector. At that size a precision or recall figure carries a wide
interval, so **every figure is reported with its denominator and a 95% Wilson interval**, per
stratum and overall. If a stratum cannot be filled, the shortfall is reported, not hidden.

### Feasibility check (counts only; nothing was selected and no detector was run)

Counted on 5 Oct 2026 with the rule above, using only `python-chess` and the puzzle file:
91,511 puzzles are tagged `hangingPiece` with rating 400 to 1199 (after de-duplication); the
theme exclusions in section 6 remove **58,724 (64%)**; the rest are all valid. Of the
remaining puzzles, those whose first solver move captures a non-pawn piece (eligible for
both detectors' real items) number **32,774**:

| Rating band | Eligible puzzles |
|---|---|
| 400-599 | 373 |
| 600-799 | 2,908 |
| 800-999 | 11,753 |
| 1000-1199 | 17,740 |

So the targets in section 7 can be met in every band, but the lowest band is thin and **the
exclusions change the mix**: most low-rated hanging-piece puzzles are also mate-in-1, and
excluding mates tilts the set toward harder, higher-rated puzzles. That is a cost of excluding
mates (question 4).

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

## 9. Hand-check protocol (owner, about 30 labels)

- A sheet lists, for each sampled item: id, the FEN, the move, the proposed label, the one-line
  reason, and a Lichess analysis-board link for that FEN.
- **Sample:** 8 real `taken`, 8 `missed` (4 real, 4 constructed), 4 `not_applicable`, and 10
  adversarial, drawn by the seeded sampler. The adversarial positions are checked in full.
- For each, mark **agree / disagree / unsure** and one sentence on any disagreement. Do not run
  the detectors while checking.
- **Pass rule:** at most 2 of the 30 disagreements and no systematic pattern. Otherwise the rule
  is revised and the set rebuilt as v2 (step 4 above). `unsure` counts as a disagreement.
- Record the result (counts, date, who checked) in the set README. "Human-reviewed" may be
  claimed only for the items actually reviewed.

## 10. What is reported

For each detector version, static-only and with engine evidence:

- Precision and recall for `missed`, with denominators and 95% Wilson intervals
- The full confusion matrix (including `uncertain` and `not_applicable`)
- Results per stratum and per rating band, and **separately for real and constructed items**
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

## 12. Questions for the owner (decisions before this is frozen)

1. Accept **constructed** `missed` items, clearly marked and reported separately? The
   alternative is no `missed` examples at all in v1.
2. Is **300 cp** the right threshold for a constructed miss, and **depth 12 or 14** for the
   engine?
3. Are the sizes in section 7 right, or would you prefer fewer items and a more thorough
   hand-check?
4. Is the **theme exclusion list** in section 6 acceptable? In particular, excluding every mate
   theme removes 64% of eligible puzzles and thins the 400-599 band to 373 (see the
   feasibility check). The alternative is to keep mate puzzles and label them `uncertain` where a
   mate competes with the free piece.
5. Who hand-checks (you only, or you plus a second reviewer such as GPT), and is **30**
   enough?
6. Should a bounded sample of real Lichess games be added later (v2) to supply real
   "ignored a free piece" and "safe move" examples?
