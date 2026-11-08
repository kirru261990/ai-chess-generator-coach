# Build plan v1 (one page)

2026-11-08 · Owner: Karthik Raman · Status: agreed in chat, draft until the open checks are done.
This replaces "validate with 15 strangers first" (ADR 0019 decisions 5 to 8, `docs/product-spec-v1.md`) for now. The reasons are in `docs/competitive-analysis-2026-11-08.md` and `docs/open-source-survey-2026-11-08.md`.

## What we are building

A training loop for the owner, delivered through the Claude connector that already exists:

1. **Find where I lose.** Import my Chess.com games; sort each into ahead, level or behind after Black's 5th move (±0.5); show the loss map.
2. **First-slip drill.** From each game, take the position just before my first big mistake, and ask for the engine-verified better move. Review on a schedule (py-fsrs). Label the slip with the opening name (Lichess CC0 opening names).
3. **Calculation drill.** From my own games, positions where I had a forcing line winning material within 1, 2 or 3 of my moves and missed it. I name candidate moves (checks, captures, threats), write the line, then see the engine's line and where mine stopped. Topped up from the public drill library when my own games give too few.
4. **Show whether I improved.** Fixed baseline, fixed rules and a start date set in advance; compare hung-piece and missed-free-piece rates (`docs/personal-study-v1.md`).

Most of 1 and 4 already exists (evidence engine, detectors, baseline windows, real-game rates, Claude connector). New work: the first-slip drill, the calculation drill, and the report.

## Not building

A coach app for everyone, a website, a conversion trainer, an LLM explainer, a puzzle generator from scratch. Others already do these (competitive analysis), and the plumbing is easy to copy.

## Order

1. **Owner:** about an hour trying the free tiers of Chessigma, Aimchess, Chessy and the Chess.com trial on the owner's account. If one already gives the loss map and first-slip drills, build only item 4.
2. **Build the first-slip drill** (short ADR, then a hand-check before it is trusted).
3. **Start the study** (date set when the first-slip drill is built).
4. **Build the calculation drill as a separate block after the study's first read,** so it does not blur the study.
5. **Only if it works,** friends try it through the Claude connector (Codex is the route for ChatGPT subscribers).

## Ranked: the items marked Next (2026-11-08)

Ranked by what each unblocks for the study, then by effort. Effort is my estimate: S under a day, M a day or two, L several days.

| Rank | Item | Part | Effort | Why this place |
|---|---|---|---|---|
| 1 | Pre-trend over all synced games | Progress | S | No code: run the evidence pass (about an hour). The study's decision rule needs the old slope first |
| 2 | First-slip drill, with the slip finder it needs | Practice | L | The one new training in the study. The finder (first big mistake per game, and the zone after move 5) is shared with ranks 3 and 5 |
| 3 | Loss map in the app | Analyze | M | Reuses the finder; shows where games are lost |
| 4 | Opening name for each slip | Analyze | S | Lichess CC0 file (66 KB); makes each first-slip drill say which opening it came from. Needs the owner's OK to download |
| 5 | Ahead / level / behind rates in Progress | Progress | M | Needs the finder and a frozen rule; secondary measures only |
| 6 | Study start date and decision rule | Progress | none | A decision: set the date once rank 2 exists |
| 7 | Convert-this-advantage game | Play | L | A second training mode; no study value until the first one has been read |

Later, not ranked: the calculation drill (after the study's first read).

## Decisions made

- Core jobs: diagnose, train from my own games, prove it. Explanations support them; reaching people in chat comes later.
- Calculation training means **forcing tactics** (a concrete line that wins something), not general plans.
- Calculation drills come from my own games first, then the public drill library.
- Reuse: py-fsrs (MIT) for review timing, Lichess opening names (CC0). Do not copy the Lichess puzzle generator (AGPL-3.0 only); reimplement the single-answer check.

## Open checks (nothing built until these are answered)

- Do the trials in step 1 change the plan?
- A forcing line needs its own definition, detector and eval before any drill is shown (ADR 0017 decision 10).
- The first-slip and calculation drills each need an ADR and a hand-check (the project's usual gate).
- Hosted connector or local Claude Desktop extension for the engine; ChatGPT plan limits (Plus and Pro) unconfirmed.
- Lichess puzzle generator and `brianch` fork licences: reimplement, do not copy.
