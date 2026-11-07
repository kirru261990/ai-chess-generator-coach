# 0018 · Drill cycles (2026-11-06)

Status: accepted by the owner in chat (2026-11-06): add a "same drills again, each pass faster" mode, with a web screen.

## Why

The owner looked at a paid 300-puzzle book series that trains tactics by repeating a fixed set in cycles (the Woodpecker idea: first pass slow, each later pass faster). We already have a drill library (ADR 0017); the repetition is the only part worth copying, and it needs no one else's puzzles.

## Decisions

1. **A set is frozen.** `drillcycle.build_set` copies up to 50 drills out of the drill bank into `cycle_set`: half hanging-own-piece (M1), half missed-free-piece (M2), one per game, easiest (lowest average rating) first, never experimental, never an M2 drill whose timing class is `unclear`. A thin type is topped up from the other. Rebuilding the bank does not change a set (tested). A new set is not offered yet.
2. **A cycle is one pass.** Cycle 1 is easiest first; each later cycle is the same drills in a new order (a seeded shuffle), so the order cannot be memorised. A cycle in progress resumes at the same position.
3. **Ledger:** `data/drills/cycles.sqlite3` (git-ignored, separate from `data/coach.sqlite3`, as ADR 0017 decision 8). Tables `cycle_set`, `cycle`, `attempt`. Cycle logic version `1` is stored with each set, next to the bank version.
4. **Matched, not correct.** An answer matches when it is an engine-verified move: M1 one of the drill's verified safe alternatives, M2 the free capture. Any other legal move is shown as "not one of the checked moves; the engine did not rule on it" (rule 5), never as wrong.
5. **Rates carry denominators** (rule 3): "matched of answered" per cycle, with the share a random legal move would match. With 50 drills a few matches either way is noise; the screen says so.
6. **Time is measured by the server**, from the first time a position is shown to the answer, capped at 10 minutes so a break is not thinking time. Speed is shown next to matches and never alone: the goal line pairs "beat 12 min" with "keep at least 41 of 50 matched". No fixed halving target is imposed.
7. **Practice, so assisted** (ADR 0005, rule 4): the answer and the engine line are shown after every move, and every attempt is stored `assisted=1`. There is no hint button, and before the answer the response holds the board, the side, the question and the legal moves only (leak test).
8. **Surface:** `GET /drills/cycles`, `GET /drills/cycles/current`, `POST /drills/cycles/current/answer`; the web tab "Drill cycles". Not exposed over MCP yet.

## What this does not show

- Getting faster on 50 repeated positions measures memory of those positions at least as much as pattern skill. It is not evidence of a higher rating, and nothing here claims it. A fresh check on drills outside the set would be needed for that.
- The drill bank was hand-checked on 40 positions (ADR 0017), mostly under 1700; "matched" inherits that.
- M2's accepted move is the engine's capture only; a second good capture the detector did not list counts as not checked.

## Reversal

Delete `drillcycle.py`, `api/drills.py`, `DrillCycles.tsx` and `data/drills/cycles.sqlite3`; nothing else depends on them.
