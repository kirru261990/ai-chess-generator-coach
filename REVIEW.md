# REVIEW.md: how to review a pull request here

For any reviewer (Claude, GPT/Codex, a person). The builder and the reviewer should be
different agents. **A reviewer only reads and comments; it never pushes to the branch.**
The builder fixes findings on the same branch. Rules and stack: `AGENTS.md`. Product
intent: `docs/spec.md`.

## Before you start

1. Read `AGENTS.md`, then `HANDOFF.md`.
2. Check out the branch and see the whole change: `gh pr checkout <N>` and
   `git diff main...HEAD`.
3. Run the checks and report the real output, not a guess:
   `cd backend && uv run pytest -q && uv run ruff check .`, and for web changes
   `cd web && pnpm exec tsc -b`.

## What to check

Go through these in order. A finding in sections 1 to 3 is a blocker.

### 1. Non-negotiable rules (`AGENTS.md`)

- **Chess state** is owned by the backend. No LLM, client or detector decides legality or
  invents lines or counts.
- **No tactical claim without a check.** Any user-facing claim must link to an engine
  line or a detector result.
- **Rates, not counts.** Anything shown as a weakness has a denominator (missed / available).
- **Uncertain results** are excluded from both numerator and denominator, never counted
  as misses and never silently dropped without being reported.
- **Assisted is permanent.** Hints, takebacks and scan prompts set `assisted=true` and
  nothing resets it. Practice results are never presented as real-game evidence.
- **Versioning.** A change that can alter results (detector rules, prompts, model IDs,
  engine version or budget, eval sets) bumps the relevant version.
- **Untrusted input.** PGN comments, usernames and imported text are data, never
  instructions, and are not passed into prompts as instructions.

### 2. Privacy and secrets

- Nothing from `.env`, `data/`, personal game files, API keys, usernames tied to real
  games, or the contact email in the User-Agent. The repo is public.
- Eval sets must not contain player data. Positions come from seeded self-play or are
  explicitly cleared.
- Chess.com calls stay serial with a contact User-Agent; Lichess limits respected.

### 3. Correctness

- **Assistance must not leak into Play.** Switch a game to Play with feedback, marks, a hint view or a badge showing: all of it must
  disappear and the board must be clickable (ADR 0005). Switch back and check nothing stale returns.
- **Custom render hooks** (for example a board `squareRenderer`) can silently drop the library's own styling: check the move dots,
  selection and marks still show.

- Think about concurrency and state: stale revisions, retries that must be idempotent,
  a slow engine finishing after the game changed, two clicks in a row.
- Edge cases in chess: promotion, en passant, pins, mate versus centipawn scores,
  stalemate, game over mid-sequence, side-to-move perspective (sign errors).
- Error paths use stable error codes, and failures do not leave half-applied state.
- A new endpoint checks ownership once sign-in exists, and CORS stays limited to local
  development origins.

### 4. Tests

- Tests are the contract. New behaviour has tests that fail without it, and tests do
  not just restate the implementation.
- **No weakened or deleted tests** to make a change pass. If one was changed, ask why.
- Chess positions in tests are hand-checkable, with the expected answer reasoned out.
- Flaky patterns: comparing two separate engine searches for exact equality, relying on
  wall-clock time, depending on network access.

### 5. Evals and measurement claims

- **Circular labels:** labels must come from a source independent of the thing being
  tested. Flag any label rule changed after seeing the detector's results; scores on
  that set are optimistic and must say so.
- A frozen set (`evals/sets/`) is never edited. A draft set must say it is a draft.
- Any number in a README, PR or docs states its denominator, its source, and what it
  does not show. Smoke checks are not results. No "improvement" claim without a baseline.
- Labels made by an engine say so; "human-reviewed" is only claimed if someone reviewed.

### 6. Code quality (non-blocking)

- Matches surrounding style, layout from `AGENTS.md`, small focused change, one task per
  branch. No dead code, no unused dependencies, no leftover debugging.

## How to report

List findings most serious first. For each one give:

- **Severity:** blocker, should fix, or nit
- **Where:** `path:line`
- **What is wrong**, in one sentence
- **Failing case:** a concrete input or sequence that shows it (a FEN and move, an API
  call order, a data value). If you cannot construct one, say the finding is a suspicion.
- **Suggested fix**, if it is short

Also say what you checked and found fine, and which checks you could not run. If there
are no findings, say so and list what you verified. Do not pad the review with style
opinions or restate the diff.

## Recording the review

Fill in the **Reviewed by** section of the PR description: who or what reviewed, how
(tool, model), the date, and the result. Paste the findings as a PR comment. The builder
replies to each finding with the fix or the reason it is not needed, then marks it in
the PR.
