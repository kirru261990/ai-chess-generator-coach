# ADR 0003 — E2 explanation eval: design, and what it cannot show

**Status:** Accepted 2026-10-07 · **Task:** T20 · **Frozen files:** see `evals/sets/e2_v1/FROZEN.md`

## What E2 measures (spec section 07)
Whether the explanations a player would see are **factually correct**, for three configurations on the same 50 positions:

| Config | What it is |
|---|---|
| `raw` | The coach model with no tools and no evidence: position and move in, explanation out |
| `grounded` | The coach's **first draft** written from the engine/detector evidence pack, **before** any verification |
| `verified` | The full harness: draft, verify, one repair, else verified facts only (what the player sees) |

`grounded` and `verified` come from the same first draft, so the difference between them is exactly the verifier.
Target from the spec: at least 98% correct checkable claims for `verified`; all three numbers are published.

## The set
50 items from the public Lichess puzzle database (CC0, ratings 400-1199), built by `evals/tools/build_e2_set.py`, which imports
no detector and no coach code. 25 **good** items (the puzzle solution, engine-confirmed within 50 cp) and 25 **bad** items (a
legal non-solution move the engine says loses 150-600 cp, no mate scores). Theme mix: 12 hanging piece, 6 fork, 4 pin/skewer,
28 other. Mate-theme puzzles are excluded because their scores are not centipawns. Nothing from the owner's own games is used
(the repository is public). Five throwaway pilot puzzles, used to debug the runner, were excluded from the set.

## How it is scored
An extraction prompt (`evals/tools/prompts/extract_v1.md`), a transcriber told never to correct the text, turns each text into
atomic claims in the verifier's claim types. Each claim is checked at Stockfish depth 18 (the verifier itself uses depth 12).
Statements the extractor cannot express (a pin, a plan, "attacks the pawn") are counted as **unverifiable**, never as
correct. Reported per config, each with its denominator and a 95% Wilson interval: claims checked, claims correct, texts
with at least one incorrect claim, unverifiable statements, empty texts, and for `verified` the status mix
(verified / repaired / fallback / unavailable). Cost in tokens and dollars is recorded.

## Decisions and their reasons
1. **The raw baseline is the same Claude model, not a GPT model.** AGENTS.md names a GPT baseline (`BASELINE_MODEL`). There is no
   OpenAI key and no `openai` dependency yet, and using the same model isolates the effect of grounding and verification from
   differences between models. A GPT baseline is still wanted and is open work; this is a recorded deviation, reversible by
   running a second raw config later. Not a stack change.
2. **No tuning after the freeze.** The coach prompt (`why_v1`), the raw prompt, the extraction prompt, the verifier version and
   the set are frozen together; their hashes are in `FROZEN.md` and a test fails if one changes. Any later change is a new
   version (`why_v2`, `e2_v2`) and a new run. The runner and extraction prompt were debugged on 5 throwaway pilot items first
   (one extraction fix: claims about the played move use the position before it).
3. **Unverifiable statements are reported, not hidden.** A config that says many things nobody can check looks good on
   correct-rate and is still violating rule 2. Both numbers are shown together.

## What this eval cannot show (read before quoting a number)
- **Not independent of the system under test.** The scorer reuses the verifier's claim checks (and so the `hanging_own` and
  `missed_free` detectors) at a higher depth. `verified` is partly graded by the logic that gates it; its correct-rate is
  therefore close to guaranteed for checkable claims. What the eval does test: how often the model says wrong things before
  the gate (`grounded` and `raw`), how much the gate costs in fallbacks and repairs, and how much goes unverifiable. A
  human review of a sample of texts, or a second independent checker, would be needed for an independent claim.
- **The extractor is an LLM** (the same model as the coach), so it can mis-transcribe in either direction. Its errors are not
  measured; a sample of extractions should be read by a person before the numbers are published.
- **Detector accuracy bounds claim accuracy.** `piece_can_be_taken` and `free_piece_available` use the same detectors scored on
  `real_play_v1`, whose real-world recall is unmeasured for missed free pieces.
- **50 positions, puzzle-derived, one run.** The "bad" moves are random engine-confirmed errors, not the mistakes a beginner makes. Intervals are
  wide. Model and engine search are not deterministic, so a re-run will differ.
- Good and bad items are engine-defined; no human has reviewed the set.

## How to run
`cd backend && uv run python ../evals/tools/run_e2.py run` (about 2 dollars; aborts above 5). Output goes to `evals/runs/` (git-ignored); the published
summary goes to `evals/reports/`.
