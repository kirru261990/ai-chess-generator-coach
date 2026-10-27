# 0011 — M3 missed threat: a third mistake type, found with a pass test

Status: accepted, 2026-10-26. Decided by: the owner (decisions 1 and 2), Claude (decisions 3 to 7, the owner may change them
after playing). Builds on ADR 0006 (PRD v2 detectors, M1 and M2).

## What M3 asks

M1 asks "did **your** move leave a piece to be taken?". M2 asks "did you miss a piece **you** could take?". M3 asks "did **their**
last move threaten something, and did you ignore it?". It ties a loss to its cause, and it sees threats that are not a simple
capture (mate, fork, discovered attack).

## The pass test

In the position after the opponent's move (player to move), the player skips a turn (`chess.Move.null()`) and the evidence engine
searches the passed position. The engine's best line there is the **threat line**; its first move is the **threat move**.

A position holds a **threat** when the player is not in check and:

1. the threat line, replayed for at most `MAX_REFUTATION_PLIES` (4), mates the player or nets the opponent at least
   `M3_MATERIAL_MIN` (2) by `line_swing`; and
2. passing costs at least `M3_THREAT_MIN_CP` (150) against the player's best move (`threat_size_cp`).

A mate counts only when the engine reports mate in at most `M3_MATE_MAX_MOVES` (2) opponent moves, which is within the ply limit.

## Outcomes for the player's move M

| Outcome | Reason codes | Rule |
| --- | --- | --- |
| `skipped` | `before_min_ply`, `in_check`, `only_legal_move`, `decided` | Gates. `M3_MIN_PLY` = 4; `decided` = best score beyond `DECIDED_LIMIT_CP` (600) |
| `no_threat` | `no_concrete_threat`, `passing_costs_little` | The pass test finds nothing concrete, or passing costs under 150 cp and the best move stops the threat line |
| `uncertain` | `threat_unavoidable` | A concrete threat, passing costs under 150 cp, and the threat line still wins after the best move: nothing saves the material |
| `met` | `defended`, `countered` | M loses under `M3_EVAL_LOSS_CP` (150). `defended` = the threat is stopped after M; `countered` = it still works (or we cannot tell) but the score holds |
| `met` | `defended_other_loss` | M loses 150 cp or more but stops the threat: the loss is another mistake (often M1), not a missed threat |
| `uncertain` | `threat_line_diverged` | M loses 150 cp or more, the pass line breaks on a later reply after M, and the engine's best line after M does not start with the threat move |
| `uncertain` | `loss_not_stable` | M loses 150 cp or more at the evidence depth but not at the stability depth (depth - 4) |
| `missed` | `all_checks_hold` | M loses 150 cp or more at both depths and the threat line still wins after M |

**Does the threat still work after M?** (PR 96 review.) The pass line holds the player's replies chosen for the passed
position, so after a real move it can break on a reply that is no longer legal while the threat stands: in a back-rank
position, ...Rb8 changes the recapture in Rd8+ Rxd8 Rxd8# but does not stop the mate. A broken replay is never taken as a
defence. In order: the pass line replayed after M wins → works; the engine's best line after M starts with the threat move →
that line decides; the threat move is no longer legal → stopped; the replay broke on a later reply → diverged (uncertain when
the loss is large). The `threat_unavoidable` check after the best move still uses the replay alone (no engine call there);
both of its outcomes are outside the rate.

The missed-threat rate is missed ÷ (missed + met). `uncertain`, `no_threat` and `skipped` are in neither part (AGENTS rule 5).

The spec's "did any top move meet the threat?" check is the `threat_unavoidable` rule above: when the best move cannot stop the
threat line, passing costs little, so the unavoidable case is found before M is looked at.

## Labels (rules only, never change the outcome)

- **Kind**, first match wins: `mate` (the line mates), `capture` (the threat move captures a player piece worth 3 or more; a
  pawn grab is labelled by what it does next, so Fried Liver Nxf7 is a `fork`), `fork` (after the
  threat move, the moved piece attacks two or more player targets worth 3 or more, or the king and one such target),
  `discovered` (after the threat move, another opponent piece newly attacks a player target worth 3 or more, or the king), `other`.
- **Origin**: `new` when the same threat line, replayed in the position before the opponent's last move, would not have won
  (mate or `M3_MATERIAL_MIN`); `standing` when it would; `unknown` when the caller does not pass that position.

## Decisions

| # | Decision | By | Why |
| --- | --- | --- | --- |
| 1 | M3 starts at ply 4 (White's 3rd move) | Owner | Early traps such as 3...Nf6?? 4.Qxf7# are common under 1000 |
| 2 | M3 material rule = 2 | Owner | A knight lost for a pawn (net 2) is a common loss under 1000; M1's rule of 3 does not count it |
| 3 | Threat size and missed loss = 150 cp | Claude | A knight for a pawn is about 2 pawns; 200 cp would cut some out. 150 is M2's loss rule |
| 4 | M3 is its own rate; the rates pass adds an `also_m1` flag | Claude | M3 now sees misses M1 skips. Revisit after the overlap check |
| 5 | A `standing` threat counts once, on the first move it is ignored | Claude | One ignored attack should not count as several misses. Applied by the rates pass, not the detector |
| 6 | Revised 2026-10-26, see below. Rates use an M3 real-game window (last 30 games per time control, frozen once) and the games after it; hand-check and tuning use older games | Claude | Same design as M1 and M2 (ADR 0006); the ADR 0002 window stays history |
| 7 | M1 and M2 do not change | Claude | Their results are frozen; `RULES_VERSION` stays 1 |

The M3 constants live in `prd_rules.py` with their own `M3_` prefix and are copied into every M3 evidence record
(`m3_thresholds`), so a later change is visible per record. Any change to them bumps `missed_threat.VERSION` and is recorded here.

## Decision 6 revised: which games (2026-10-26, TASKS M3b)

Decision 6 first said the rates would use the 100-game window of ADR 0002. That was wrong for this repo: the real-game rates
(`realgame_rates`, ADR 0006 decisions 4 and 41) never use that window. Each mistake type freezes its own window: the last
`WINDOW_GAMES` (30) games per time control before a moment, once, and the database refuses any edit or delete. M1 and M2
freeze at their first practice session. **M3 has no practice yet, so its window is frozen by an explicit command**,
`realgame_rates freeze`, run once before any M3 training (MVP 1 and 2). `run` and `report` never freeze it. The post window is
every game from the freeze on, as for M1 and M2. The hand-check sample (TASKS M3d) uses games outside both windows.

## How M3 is counted in the rates (TASKS M3b)

- Schema v11: `baseline_window` and `realgame_game` accept `M3` (rebuilt with every row copied; triggers re-created).
  `realgame_game.details_json` holds the M3 breakdown: missed by kind and by origin, `also_m1`, met and uncertain reasons,
  no-threat and skipped counts, and repeats. NULL for M1 and M2.
- Per row: `counted` = missed + met (threats faced), `events` = missed, `uncertain` = uncertain, `skipped` = no threat,
  gates and repeats. The rate is events ÷ counted, with the M2 floor (20 opportunities per window).
- **Decision 5 in code:** a repeat is the **same** ignored threat: the threat is `standing`, the previous player move
  `missed` a threat, and both have the same threat move. It is skipped and logged in `repeats`, whether the player misses it
  again or finally meets it. `standing` alone is not enough (PR 97 review): with two threats on the board, the pass search can
  pick threat A on one turn and threat B on the next, and B is a new opportunity. A standing threat's line already worked
  before the opponent's last move, so the same threat keeps its first move. A record with no threat move is never a repeat.
- **`also_m1`:** a missed threat on a move that `hanging_own` v4 called a `mistake`. M1 starts at ply 8, so misses at plies
  4 to 7 are never `also_m1`.
- The Progress screen and its endpoint keep M1 and M2 only; M3 is read with `report --types M3` until it has a screen.

## Hand-check result (2026-10-27, TASKS M3d): the gate was not met

The owner judged 30 flagged moves from games older than the M3 window (15 per time control, one per game; `handcheck_m3.py`,
questions A "could they win material or mate if you had skipped your turn?", B "can they still do it after your move?", C "could
you have stopped it with another move?"). A flag is real only with yes to all three. **14 of 30 were real; the gate is 27.** 10|0 7
of 15, 15|10 7 of 15. A 95% Wilson interval for 14 of 30 is about 0.30 to 0.64.

Where the 16 went wrong (the first "no" on each): A no 7 (the owner sees no threat), B no 5 (the owner says the move stopped it,
the detector says it still works), C no 4 (the owner sees no other move that would have stopped it).

Breakdown (the numbers are small; read them as leads, not findings):

| By | Real / flagged |
| --- | --- |
| kind `mate` | 3 / 3 |
| kind `capture` | 7 / 15 (5 of the 8 misses are B no) |
| kind `fork` | 3 / 6 |
| kind `other` | 1 / 5 (4 of the 5 are A no) |
| kind `discovered` | 0 / 1 |
| origin `new` | 13 / 24 |
| origin `standing` | 1 / 6 |
| also flagged by M1 | 5 / 7 |

The size of the loss (230 to 1517 cp) and of the threat (298 to 1516 cp) do not separate real from not real, so the thresholds are
not the obvious cause. The owner's reasons for each "no" are not recorded; they are the next thing to learn.

**What this means.** M3 v1 is not accurate enough on real games to be shown as a weakness. The eval-set score (precision 0.99, recall
0.95 on `missed_threat_v2`) and this result disagree: the set holds puzzle positions with clean, immediate captures and mates, and
real games are messier. That is a finding about the set as well as the detector. Nothing was changed after seeing the answers.
Per AGENTS rule 5 and the gate, the M3 rate (TASKS M3e) is not to be reported as a weakness, and the detector is not to be retuned on
these 30 positions and then scored on them again.

**Ways forward (owner decides).** (1) Record the owner's reason for each of the 16 (especially the 5 B no and 7 A no). (2) Find the
common cause; candidates to check, none decided: `standing` threats (1 of 6 real), `other` kind (1 of 5), and how "still works after
the move" is read when the move is itself a capture or check. (3) A change is a new detector version (`missed_threat` v2) with its own
eval and a **new** hand-check sample of different older games (about 350 remain unsampled), gate 27 of 30 again.

### Why the 16 were not real (the owner went through them, 2026-10-27)

Two separate causes, found after the score (so they guide a fix and cannot be tuned on these 30):

1. **The loss was not caused by the threat (9 of 16: hc3-02, 03, 08, 11, 15, 20, 21, 26, 28).** In these the engine's best reply to the
   player's move is not the flagged threat; the move allowed something else (hc3-02: f3 attacked the queen but left a bishop
   undefended, and the queen took it with check). The detector calls a move `missed` when the move loses at least 150 cp and the
   threat line still wins after it (`threat_after_move` = works), and never checks that the loss comes from that threat. In the 14 real
   flags the engine's best reply was the threat in 13; in the 16 not-real in 7. This is a detector defect, not a question problem.
2. **The questions were misread (6 of 16: hc3-05, 06, 07, 12, 13, 18).** For each, the owner explained that they agree with the
   engine: the threat was real and they missed it (06, 07, 12, 13, 18), or a counter-attack answers it (05). Question C ("could you
   have stopped it with another move?") was read as "stopped completely" and B ("can they still do it?") as "can I recover". On
   hc3-18 the owner had not seen the pin when answering A. These flags were right; the page's wording failed.
3. **A real miss the owner had not seen (1 of 16: hc3-27).** The owner saw no threat (A no). The threat is a discovered attack: the
   black pawn steps from e5 to e4, hitting the queen and opening the bishop's line to the rook on a1. The flag was right.

By the owner's own explanations, 21 of 30 were right (14 real by the answers, plus these 7), 9 were a detector defect. The recorded
result stays 14 of 30 and the gate is not met; the 21 is a reading, not a score. A re-run must use a new sample.

**Next (owner decides).** (a) `missed_threat` v2: `missed` only when the engine's best reply after the move starts with the threat
move (or the loss is otherwise explained by the threat), with its own run on `missed_threat_v2` and a new unsampled hand-check
(about 350 older games remain). (b) New hand-check wording, plain and one fact per question, for example "What can they do next if
you had skipped?" / "Does your move stop it, or answer it with something bigger?" / "Did you miss it?"; shown with the move
in words. (c) Do not report an M3 rate as a weakness until both pass the gate.

## Not in this step

The frozen `missed_threat_v1` eval set and the hand-check page come in later pull requests.

## Reversal

Delete `detectors/missed_threat.py`, `detectors/threat_kind.py` and the `M3_` constants. Nothing else reads them yet.
