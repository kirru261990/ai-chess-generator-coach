# missed_threat_v1: label rule (written before any detector ran on the set)

**Purpose:** measure how accurately `missed_threat` (M3, ADR 0011) separates a player who **ignored a threat** from one who
met it, had none to meet, or could not have stopped it. It measures detection accuracy only. It does **not** measure how often
players miss threats: puzzle positions are curated tactics, so threats are far denser than in normal play.

Item = `(fen, move_uci, ply)`: the position after the opponent's move, the player to move, and the move played. Labels:
`missed`, `met`, `uncertain`, `not_applicable` (the detector's `no_threat` and `skipped` both count as `not_applicable`).

## Independence
The builder (`evals/tools/build_missed_threat_set.py`) imports nothing from `app/detectors/` (a test enforces it). It uses Lichess
puzzle data (CC0; each puzzle's solution, themes and rating are Lichess's), the separate exchange search in
`build_real_play_set.py` (full search over captures and recaptures, not the detectors' cheapest-attacker code), `python-chess`,
and Stockfish at depth 14. The engine's pass search is used to confirm that a threat exists where no capture or mate shows it
statically; the detector uses the same idea, so agreement on those items shows the detector is implemented as specified, not that
the idea is right. Every item records which kind of evidence supported its label (`threat_basis`: `static` or `engine_only`).

## Definitions (numbers are the label rule's own; they match ADR 0011's detector numbers on purpose)
- A **static threat** is a move of the opponent, after the player passes, that wins at least 2 pawns of material by the exchange
  search (a capture of a non-pawn piece, after best recaptures) or gives checkmate.
- An **engine threat**: passing costs the player at least 200 cp (best move versus pass, depth 14). "No threat" needs no static
  threat and a pass cost under 60 cp. Items in between are left out.
- **Decided** positions (best-move score beyond 600 cp either way), positions in check, positions with one legal move and plies
  below 4 are never in the set (the detector skips them; ADR 0011).
- Losses are depth-14 engine losses against the best move, from the player's side; a mate is clamped to 10000.

## Categories
| Category | Label | Source and rule |
|---|---|---|
| `missed_real` | missed | Lichess puzzle: X is the side that played `Moves[0]`; item = (position before `Moves[0]`, `Moves[0]`). The solver's reply `Moves[1]` already won when X passed (static threat) and still wins after `Moves[0]`; the move loses at least 300 cp; the engine's best move stops that threat. A real human move that ignored a real threat. |
| `met_real` | met | `defensiveMove` puzzle: item = (position after `Moves[0]`, `Moves[1]`). Passing costs at least 200 cp (engine threat; a static threat is recorded when there is one) and the solution loses under 100 cp. |
| `constructed_missed` | missed | Same positions as `met_real` (different puzzles) with a random legal non-solution move that leaves a static threat working and loses at least 300 cp. Constructed, not real behaviour. |
| `constructed_quiet` | not_applicable | A puzzle's first position: no static threat, no capture worth 1 pawn or more, pass cost under 60 cp; the move is the engine's best. |
| `hung_not_threat` | not_applicable | Same kind of position, with the real `Moves[0]` that hangs a piece (M1-type blunder, loses at least 300 cp). Nothing was threatened before the move, so M3 does not apply. |
| `quiet_blunder` | not_applicable | Same, but `Moves[0]` allows another tactic without hanging a piece. |
| `adversarial` | any | Hand-built or opening-line positions with a written reason; each is also checked by the same independent rules. |

One puzzle supports at most one item. Real items are drawn evenly from the rating bands 400, 600, 800 and 1000 (200 wide) with
a fixed seed (`20261026`). Puzzles tagged with deliberate-sacrifice themes are **not** excluded here, because the first move
`Moves[0]` is a real blunder, not a sacrifice; the threat checks decide eligibility.

## Known limits (stated before scoring)
- `missed_real` items need a threat that is a capture or mate in one that was available before X's move; forks, discovered attacks
  and quiet threats are covered only by the `engine_only` items of `met_real` and by a few adversarial items.
- `constructed_missed` uses only static threats.
- No human has reviewed the labels; the hand-check page for real games (TASKS M3d) is a separate step.
- Positions come from puzzles, so they are tactically rich; the set cannot give a rate of ignored threats in normal play.

## Scoring (fixed before the run)
Positive class `missed`. Precision = labelled-missed among detector-missed; recall = detector-missed among labelled-missed; each
with a 95% Wilson interval, for all items and for real, constructed and adversarial items separately. Targets (TASKS M3c):
precision at least 0.90, recall at least 0.85. The uncertain rate and every disagreement are reported. Nothing is tuned on the
set; a change to `missed_threat` after seeing the scores means a new detector version and a new run on a new set.
