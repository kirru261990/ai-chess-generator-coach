# ADR 0004 — E2 v2: what changed after the first run, and why a new set

**Status:** Accepted 2026-10-08 · **Task:** T35 · **Follows:** ADR 0003 and `evals/reports/e2_v1_2026-10-07_notes.md`

## What the first run found (e2_v1)
`verified` scored 93% of checkable claims (target 98%, not met). Reading the wrong claims: most were the claim extractor
over-reading the text; 2 or 3 were real, mostly **move sequences named in the text in an order that is not legal**, which the
verifier never checked; and many statements stayed unverifiable (68 in `verified`).

## Changes (each a new version; the v1 files are untouched and still frozen)
| Part | Change |
|---|---|
| Verifier v2 | A sentence that names two or more moves as a line of play must match a verified `line_legal` claim or an engine line, in that order and contiguous (`check_sequences`) |
| `why_v2` | Coach prompt: write a sequence only with a matching `line_legal` claim and no skipped moves; evaluation words and "free/hanging/can be taken" need matching claims; advice only when it follows from the evidence, no generic tips |
| `extract_v2` | Extractor must be literal: no `eval_band` from words like "blunder" or "cost", no free-piece reading from "could capture", lines contain exactly the moves the text names |
| Runner | `run_e2.py` takes a set name, and `rescore` re-scores saved texts with the current extractor |

## Development run, on the e2_v1 positions (these positions were already seen, so this is tuning, not a result)
Same 50 positions, new stack: `verified` **119/119 (100%)**, `grounded` 122/124 (98%), `raw` 118/163 (72%). Unverifiable
statements in `verified`: 22 (was 68). To separate the instrument from the coach, the old v1 texts were re-scored with `extract_v2`:
`verified` 131/138 (95%), `grounded` 135/140 (96%), `raw` 74%. So the stricter extractor alone moved `verified` from 93% to
95%; the rest of the gain on these positions (95% to 100%) is the new prompt and verifier, and it was measured on the
positions the changes were designed against. One text per config could not be extracted and is reported as not scored.

## Why a new set (e2_v2)
The instruments were changed after the v1 results were seen. Quoting a v2 number on the same 50 positions would be tuning on
the test set. `e2_v2` is 50 **new** puzzle positions (new seed, none of the v1 or pilot puzzles), frozen together with
`why_v2`, `extract_v2` and `raw_v1` **before** the final run. Nothing is tuned after that.

## What does not change (read ADR 0003)
The scorer is still not independent of the verifier; the extractor is still the same model and unreviewed by a person; the raw
baseline is still the same Claude model; no human has reviewed the items. A fresh result of 98% or more would show the
checkable claims are right, not that the explanations are complete or useful: statements that cannot be checked are still reported
separately and are still many.

## Expectation recorded before the final run
Target unchanged: at least 98% of checkable claims correct for `verified`. If it is missed, that is reported as missed. With about
120 claims, even a perfect score has a lower 95% bound near 97%; the report states the interval, not only the rate.
