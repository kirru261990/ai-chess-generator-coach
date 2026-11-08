# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary:** recreational chess players rated 300–1800 on Chess.com or Lichess. Design decisions serve this whole band from now on, not only the owner. They lose games to the same tactical misses, mostly hanging pieces and missed threats, because they do not check the board before moving. They play rapid games and want to stop repeating those mistakes.

**Pilot reality:** today the only active user is the owner (Chess.com, rated about 570, 10-minute and 15+10 rapid). A few invited friends follow. Sign-in and per-user data do not exist yet, so every screen currently serves one person.

**Job:** "Show me the mistakes I keep making in my real games, train me on them, and prove whether I stopped."

## Direction update (2026-11-07, ADR 0019)

The product now focuses on the **middlegame (move 5 onwards, in this product's sense; amended 2026-11-08, was move 11)**: turning a good opening into a won game, for players rated 500 to 1600. The headline outcome is **conversion rate**, with mistake rates as the diagnosis. The first step is a validation test (username, conversion report, drills, play, website plus chat), not the full product. Where this section differs from the text below, this section wins. See `docs/product-spec-v1.md` and `GLOSSARY.md`.

## Product Purpose

The coach plays, analyses the player's games, finds the mistakes they repeat, trains them on those mistakes, and measures whether the mistakes fall in later real games.

Success means the player makes a repeated mistake less often in real games. The coach succeeds when the player needs less coaching, not when the player asks for more hints.

Secondary purpose: a portfolio-grade AI system (a tool-using coach agent, evals, an MCP backend, a measured learning outcome). Revenue is not a goal now.

## Positioning

Two claims together, which neighbouring products cannot truthfully make:

1. **Proof.** Every coaching explanation is checked against the chess engine and rule-based detectors before the player sees it. Progress is measured in the player's real games, with denominators, not in puzzle scores.
2. **The player's own mistakes.** Training uses positions from the player's own games and their own mistake types, not a generic puzzle feed.

## Operating Context

- **Laptop browser:** the main surface. The web app with tabs Play, My mistakes, Review, Blind spots, plus Practice and Progress screens.
- **Claude and ChatGPT chat:** through the MCP connector, with an interactive board inside the chat. Practice, Play and assisted games run there.
- Phone and tablet use is not a confirmed context yet.
- Games come in by sync from Chess.com. Lichess sync and PGN import are planned, not built.
- The core loop: played game → verified mistake → replay in Practice → delayed unseen test (72 hours later) → recurrence check in later real games.

## Capabilities and Constraints

- **Play vs Practice.** Play counts as real evidence and shows no help. Practice is always marked `assisted`. All help (verdicts, evaluation bar, board marks, badges, hints, undo, threat warnings, coach explanations) exists only in Practice (ADR 0005).
- **The backend owns chess facts.** The LLM never decides legality, never invents lines and never produces counts. It only words facts that Stockfish, the detectors and the rules engine have verified.
- **Rates, not counts.** A weakness is always shown as missed / available, with the denominator. Five-position tests show direction, not proof, and the UI says so.
- **Abstain rather than guess.** Uncertain detector results leave both numerator and denominator.
- **Tests are unassisted.** Starting and delayed tests give no help or feedback until the final submit.
- **Mistake types in scope:** hanging own pieces, missed free pieces, missed threats; simple forks later.
- **Model spend is capped** by a monthly budget; without budget the coach shows checked facts only.
- **Undecided:** sign-in and multi-user data, mobile layouts, a stable public address for the private connector, Maia-2 as opponent.

## Brand Commitments

- Name: **AI Chess Coach**.
- Voice: plain and honest. Say what is known, with its denominator; say what is uncertain once. Warm about real progress, never inflated.
- Fixed terms: Play, Practice, assisted, verdict (best, good, book, slip, mistake, blunder), blind spot, starting test, delayed test, denominator.

## Evidence on Hand

- A frozen baseline of the owner's 100 most recent rapid games and its frozen results (`docs/decisions/0002-baseline-window.md`; data itself is local and never committed).
- Explanation accuracy eval E2 v2: 110 of 110 verified on the frozen set (`evals/reports/`; read the notes before quoting).
- Detector scores on the frozen `real_play_v1` set (`evals/reports/real_play_v1_2026-10-06.md`).
- Absent, and must not be fabricated: testimonials, user counts beyond the owner, measured rating gains, comparisons with other products.

## Product Principles

1. **Verified or silent.** If a claim cannot be checked, the coach does not make it.
2. **Help is visible as help.** Assisted work is always labelled and never counts as evidence.
3. **The player's own games come first.** Training material starts from the player's real mistakes.
4. **Every number has a denominator.** No bare counts, no unearned confidence.
5. **Less coaching is the win.** Design for the player to need fewer hints over time.
