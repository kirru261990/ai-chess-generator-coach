# missed_threat_v3: label rule (written before the set was built or any detector ran on it)

**Purpose.** Measure `missed_threat` v2 (ADR 0013) on **real games** by players rated 600 to 1200, which the puzzle sets (v1, v2) could
not do (their score of 0.99 / 0.95 did not carry over to the owner's games: ADR 0011). Item = `(fen, move_uci, ply)`: the position
after the opponent's move, the player to move, the move played. Source: Lichess standard rated games, Rapid, both players 600 to 1200,
normal ending, 20+ moves (CC0), the start of 2026-09 (`evals/tools/lichess_stream_sample.py`). One item per game.

## Independence
`evals/tools/build_missed_threat_set_v3.py` imports nothing from `app/detectors/`. It uses `python-chess`, the exchange search in
`build_real_play_set.py` (full captures and recaptures), the helpers of `build_missed_threat_set.py` and Stockfish at depth 14. The
detector runs at depth 18 with its own rules, so the two are different code at different depths. **Limit, stated now:** the forced-threat
test below is the same *idea* as ADR 0013, so engine labels can only check that the detector implements it, not that it is the right idea.
The right-idea check is the owner's page (below).

## Definitions (depth 14, the player's side; mate clamped to 10000)
- `best` = the engine's best score; `L` = best minus the score after the played move M; position must be calm (`|best| <= 400`).
- **Static threat** = a move T of the opponent, after the player passes, that wins at least 2 pawns by the exchange search (a capture
  of a non-pawn piece after best recaptures) or gives checkmate. No threat = no static threat and pass cost under 60 cp.
- **Forced-threat loss (FTL)** = `best` minus the score of the position after M and then T (T must be legal after M).
- **Avoidable** = after the engine's best move B, T is illegal or `best` minus the score after B and T is under 100 cp.

## Labels
| Label | Rule (all must hold) |
|---|---|
| `missed` | a static threat T; `L >= 300`; T legal after M; `FTL >= max(250, 0.6 * L)`; avoidable. (Margins above the detector's 150 and 0.5 on purpose, so labels sit away from its cut-offs.) |
| `uncertain` | a static threat T; `L >= 300`; T legal after M; `FTL < 100`: the move lost for another reason (the case ADR 0013 abstains on). Detector `loss_not_from_threat` maps to this label. |
| `met` | a static threat T with pass cost at least 200 cp; `L < 100`. |
| `not_applicable` | no threat (see above). Half have `L >= 300` (a blunder with no threat to meet), half `L < 100`. |
Anything in between is left out. The detector's `no_threat` and `skipped` map to `not_applicable`; `uncertain` to `uncertain`.

## Quotas and sampling
Target 30 `missed`, 15 `uncertain`, 25 `met`, 30 `not_applicable`; fixed seed `20261030`; games taken in shuffled order, the first
qualifying position per game. Shortfalls are reported in `provenance.json`, not filled with constructed items. Only static threats
are used (as in v1), so quiet engine-only threats are not covered; this is a stated limit.

## The owner's check (fixed before the page is shown)
The owner sees a **sample of 24 items** (8 `missed`, 6 `uncertain`, 5 `met`, 5 `not_applicable`, labels hidden) and answers, in plain
words, for the side to move X and the opponent Y: **A** "If X did nothing, could Y next win a piece or give checkmate?" **B** "After X's
actual move, can Y still do that?" **C** "Could X have played a different move that avoids or answers it?" **D** "Does X's move lose
something else that has nothing to do with this threat?" Each: yes / no / can't tell.
Mapping to a label, **frozen here**: `missed` = A yes, B yes, C yes, D no. `uncertain` = A yes, B yes, C yes, D yes. `met` = A yes, B no.
`not_applicable` = A no. Any "can't tell" in a needed answer = the owner could not judge that item.
**Use:** an item where the owner's mapped label differs from the engine label is **removed** from the set (and listed in `provenance.json`
with both labels); it is never relabelled to fit the detector. If the owner agrees with fewer than 20 of the 24 (about 83%), the engine
labels are not trusted and the set is not frozen. The check covers only the 24 sampled items; the rest rest on the engine labels.

## Scoring (fixed before the run)
Positive class `missed`. Precision and recall with 95% Wilson intervals for all items, the `uncertain` and `met` rates, and every
disagreement. Targets as for v1 and v2: precision at least 0.90, recall at least 0.85. Nothing is tuned on the set; a change to
`missed_threat` after seeing scores means a new detector version and a new set. This set measures detection accuracy on real games, not
how often players miss threats (items are chosen by quota, not by chance).
