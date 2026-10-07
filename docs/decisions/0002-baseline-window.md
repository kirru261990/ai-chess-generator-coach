# ADR 0002 — The baseline window

**Status:** Accepted and **frozen 2026-10-07 (00:11 UTC)** · **Decided by:** the owner ("freeze it"), on Claude's proposal
**Where the data is:** `data/baseline/baseline_window_v1.json` on the owner's Mac (git-ignored, read-only). **The game ids are not in this repository.**

## What the baseline window is
The fixed set of the owner's own games that is measured **before any coaching**, so later games can be compared with it
(spec section 08). Freezing it first is what stops anyone, including us, from choosing games after seeing the results.

## What was frozen
- **Rule:** the 100 most recent case-study games (Chess.com rapid 10|0 and 15|10) by end time, taken from the 450 synced
  on 2026-10-05. Ties on end time are broken by game id.
- **Size and mix:** 100 games, **50 at 10|0 and 50 at 15|10**. Span: 30 August to 5 October 2026 (about five weeks).
- **Fingerprints (sha256 of the sorted ids, one per line):**

| List | Games | sha256 |
|---|---|---|
| Whole window | 100 | `87217bafab5d81e58b8214075642251858f1bff39adb3026a168120d3089aa7b` |
| 10\|0 only | 50 | `7ac385a0c9c94a29138afe9fc0159122e0a7d2e760a39a3bd7cab847455cc4c2` |
| 15\|10 only | 50 | `01b8d1cb4c22fadbdf93e685c614fc79c5e732b79791d45153c23a2f92791aad` |

- **Check it:** `cd backend && uv run python -m app.learner.baseline verify` recomputes every fingerprint from the stored ids.
  The freeze command refuses to overwrite an existing file, and the file is read-only.

## Decision: the two time controls are kept apart for now
The owner asked to keep the 10|0 and 15|10 work separate. **Interpretation (Claude's; "10/10" was read as 10|0):**
- The window is frozen as **two lists with their own fingerprints** inside one file.
- **Results are reported per time control only; no pooled headline figure for now.** The spec (D7, section 08) asks for each
  separately *and* combined; the combined figure is deferred, not dropped.
- **Coaching focus is chosen per time control** (spec D6 says one focus at a time): a 10|0 focus and a 15|10 focus, not one
  shared plan. The blind-spot map shows them separately.
- Reason this matters anyway: 15|10 gives more thinking time and usually fewer misses, so a pooled rate would mix two different
  behaviours, and the mix itself would move it.
- **Reversible:** nothing is lost by this. Both lists and the whole are frozen, so a pooled figure can be computed later from the
  same data. Reverse it by adding the combined report and the shared plan.

## Rules while this is frozen
1. `data/baseline/` is never edited (AGENTS.md). A different window means a new file (`..._v2.json`) and a new ADR, not an edit.
2. **Do not use the coach on these 100 games** (review moments, "why?" explanations, practice built from them) until the baseline
   *results* are computed and frozen (T14, then T15). Running the detectors for T14 is the measurement itself and is allowed once.
3. After that, these 100 games stay out of every later comparison window, which must contain only newer games.
4. Only counts and fingerprints may appear in the repository, in reports and in write-ups. Not the ids, and not the games.

## Known limits
- Short window (about five weeks), and the owner's rating moved during it, so "before" is a short stretch, not a long average.
- 100 games is enough for a first measurement, not for confident small differences; every figure will carry its denominator and an
  interval, and results below the minimum sample are labelled "early signal" (spec D7).
- Detector results for these games do not exist yet: that is T14.
