# The build loop

Agreed with the owner on 2026-11-08. One loop per feature, picked from the ranked list in `docs/build-plan-v1.md` (status on the Chess Coach Map page). Each step has a skill and a written output. The loop ends in the owner's real games, not at merge.

| Step | Skill | Written output | When |
|---|---|---|---|
| 1. Challenge | First Principles (deconstruct, challenge, reconstruct) on the feature's one-line claim | The claim split into hard constraint, soft constraint and assumption, with the cheapest test of each assumption | L items, or anything that changes the study. Skip for S items |
| 2. Define | Matt Pocock `/grill-with-docs` (`research` when a fact is missing) | Terms in `GLOSSARY.md`, an ADR in `docs/decisions/`, and an explicit "does this touch the study?" answer | Always |
| 3. Design | Impeccable (`DESIGN.md`, `PRODUCT.md`), plus `prototype` when the screen or state model is unclear | A screen agreed before any code | Only if the feature has UI |
| 4. Build | Matt Pocock `tdd`; `codebase-design` for a new module; `diagnosing-bugs` when something is red | Tests first, then code, on a feature branch | Always |
| 5. Review | Matt Pocock `code-review` (standards and spec reported separately); Impeccable critique or audit for UI; then `pr` | Findings fixed; a PR body with evidence and merge danger | Always |
| 6. Prove | First Principles applied to the result | Map page, `HANDOFF.md` and the ADR updated, and a note on what the study will measure | Always |

## Rules

- **Size rule.** S items (under a day) run steps 2, 4, 5 and 6. L items run all six.
- **Practice, not Play.** New training features go in Practice (assisted), under ADR 0005. Results from them never count as evidence.
- **Step 6 is where the study lives.** A feature is done when the pre-registered rates in `docs/personal-study-v1.md` can show whether it helped, not at merge.
- **Quarterly.** Re-run the competitive-analysis process against `docs/competitive-analysis-2026-11-08.md` and refresh the watchlist.
- The rules in `AGENTS.md` still apply: branches and PRs, tests, licences, versioning, `HANDOFF.md` at the end of a session.

## What is installed

Matt Pocock's skills (the `mattpocock-skills` plugin) and Impeccable are installed in the owner's Claude Code. First Principles and the competitive-analysis process are not: they were fetched from GitHub and applied by hand (`docs/competitive-analysis-2026-11-08.md`, ADR 0019). `/to-spec` and `/to-tickets` are named in `AGENTS.md` but did not show in the session's skill list on 2026-11-08; check before relying on them.
