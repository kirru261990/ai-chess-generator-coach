## Summary
<!-- What changed and why, in a few lines. Link the task (TASKS.md ID) if there is one. -->

## Review guide
<!-- Which files to read first. -->

## Test plan
- [ ] `cd backend && uv run pytest -q`
- [ ] `cd backend && uv run ruff check .`
- [ ] `cd web && pnpm exec tsc -b` (web changes)
- [ ] Tried it by hand where it affects the UI
<!-- Paste real results, for example "91 passed". -->

## Caveats
<!-- Anything a reader should not over-trust: unreviewed labels, optimistic numbers, known gaps. -->

## Definition of done
- [ ] Tests and lint pass
- [ ] `HANDOFF.md` updated
- [ ] No secrets, `.env`, `data/` or personal games committed
- [ ] Any change that affects results has bumped its version

## Reviewed by
<!-- The builder and the reviewer should be different agents. The reviewer follows REVIEW.md
and only comments; it does not push to this branch. -->

- **Reviewer:** <!-- e.g. GPT-5 via Codex CLI, Claude /code-review, a person -->
- **Date:** <!-- YYYY-MM-DD -->
- **Method:** <!-- tool and how it was run, e.g. "@codex review", "codex CLI on a local checkout" -->
- **Result:** <!-- no findings / N findings: N fixed, N not needed (reason) / not reviewed -->
- **Findings:** <!-- link to the review comment -->
