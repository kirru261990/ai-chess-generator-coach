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
- **Decision 5 in code:** a `standing` threat after a player move that was `missed` is a repeat of the same ignored threat:
  skipped and logged in `repeats`, whether the player misses it again or finally meets it.
- **`also_m1`:** a missed threat on a move that `hanging_own` v4 called a `mistake`. M1 starts at ply 8, so misses at plies
  4 to 7 are never `also_m1`.
- The Progress screen and its endpoint keep M1 and M2 only; M3 is read with `report --types M3` until it has a screen.

## Not in this step

The frozen `missed_threat_v1` eval set and the hand-check page come in later pull requests.

## Reversal

Delete `detectors/missed_threat.py`, `detectors/threat_kind.py` and the `M3_` constants. Nothing else reads them yet.
