# 0021 · Slip cause and drill timer (2026-11-09)

Status: accepted; backend built on `feat/slip-cause-timer` (2026-11-09): `slipcause.py`, timer in `slipround.py`, `?timer=` on the current-position route. The web screen (countdown, cause card) needs the Design step first. The owner answered the grilling questions Q1 to Q5 in chat on 2026-11-09 ("yes"). Extends ADR 0020 (first-slip drill) and follows ADR 0005 (practice is assisted) and ADR 0018 (server timing, leak test).

## Why

Two things the owner said while checking the first-slip hand-check: a drill should teach a **principle** ("why does the computer prefer this?"), and the owner plays 10-minute rapid games (about 15 seconds a move), so practice with no clock can build a habit that loses on time.

## Decisions

1. **Cause labels come only from detectors.** After a drill is answered it carries one cause: `hanging_own` (the move left a piece to be won; `hanging_own` v4), `threat` (it ignored the opponent's threat; `missed_threat` v4), `missed_free` (it passed up a free capture; `missed_free` v3), or `other`. `other` means no detector confirmed anything: the drill then says so and gives no reason (AGENTS rule 5). A detector result of `uncertain` gives `other`, never a guess. If several detectors confirm, the first of that order wins: `hanging_own`, `threat`, `missed_free`. There is no fork detector in the current set, so there is no fork label.
2. **Where labels live.** In their own file, `data/drills/slip_causes_v1.json`, keyed by drill id, each with the detector name and version. The drill file is not rewritten, so `bank` stays `1` and no drill is rescanned. A label from an older detector version is not served (the drill shows `other` until relabelled). An `other` label records the whole detector set it was judged under (`hanging_own@4+threat@4+missed_free@3`) and is served only while that set is current. Labelling reads the evidence cache, so it is cheap after the build.
3. **The cause is shown after the answer only.** The response before the answer is unchanged: board, side, question and legal moves (the leak test of ADR 0018 stays).
4. **The timer is a countdown on each position,** default 15 seconds (the owner's average in a 10-minute game), with 8 seconds ("pressure") and no timer ("learning") as options. It is always visible. When it runs out the position is marked over time, but the owner can still answer.
5. **The server decides whether the answer was over time,** from the time between showing the position and receiving the answer (the existing `elapsed_ms`), not from the browser's clock. Each attempt stores the timer setting and `over_time`.
6. **The study is not touched.** Every drill attempt is already assisted and never evidence (ADR 0020). Built now: each attempt stores its timer setting and `over_time`, and the round summary counts over-time answers and answers per setting. Showing the over-time share and seconds on the progress page, split by timer setting, is part of the web step. Round version `2` marks rounds that had a timer (version `1` rounds had none), so older rounds stay traceable.

## What this does not show

A label says which pattern the detector found in that move, not why the owner played it. A fast, matched answer in practice does not show the same speed in a game.

## Reversal

Remove the labels file and the timer columns; the drills and rounds of ADR 0020 are unaffected.
