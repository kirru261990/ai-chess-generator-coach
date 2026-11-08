# Middlegame Conversion Coach: Validation Spec v1

**Date:** 2026-11-07 · **Owner:** Karthik Raman · **Status:** draft for the owner's review · **Decisions:** ADR 0019 · **Terms:** `GLOSSARY.md`

This spec covers only the **validation build**. It does not replace `docs/spec.md` v0.4; where they differ, ADR 0019 wins.

## 1. Problem

Players rated 500 to 1600 reach a good position after the opening and still lose it. Many apps teach openings, endgames or puzzles; almost none train the middlegame (move 5 onwards) with the question "how do I convert what I have?" (the competitor scan found conversion features, so this is no longer a "nobody does it" claim). Owner's data at the checkpoint after move 5, ±0.5: 196 of 618 games ahead, 117 won and 70 lost (ADR 0019 amendment, 2026-11-08).

## 2. Claim to validate

> Players rated 500 to 1600 find a report of their own conversion games useful, and come back to train on it.

Not claimed: that the product raises ratings.

## 2b. Evidence so far and hypotheses (ADR 0019, 2026-11-07)

On the owner's 584 usable games, squandered advantages are 28% of losses; 45% are lost from a bad position after move 10. Detectors give a verdict on only about a third of squandered advantages (mostly hung pieces). Hypotheses H1 to H5 and their status are in ADR 0019. **Open for the owner:** build the test product as a conversion report (section 3 below) or as the proposed loss map (all three zones); section 3 is written for the conversion report until decided.

## 3. The test product

| Part | Behaviour |
|---|---|
| Entry | Enter a Chess.com username. No sign-in. Last 20 rapid games (10 minutes or more). |
| Conversion report | Headline "N of your last 20 games were good openings; you won M" (zone taken after Black's 5th move at ±0.5, with the ±1.0 version beside it). Up to three squandered advantages, turning point on a board. A reason only when a detector (M1, M2) supports it; otherwise the engine's better move and "no reason was checked". |
| Drills | Five. Order: own drills, then public drills, then generated drills (ADR 0019 decision 9). Each labelled own / public / generated. Tap-a-square answers, matched not correct. |
| Play | Play vs Stockfish or Maia: level and colour chosen by the player. Two modes: normal game, and convert-this-advantage game. Maia only for supported bands. |
| Surfaces | One-page website, and the Claude connector (ChatGPT smoke test first). Same service behind both. |
| Waiting | Report may take minutes; page can be left and reopened. |
| Not in the test | Accounts, saved history, Layer 2 habits, Lichess, delayed tests, progress screen, M3. |

## 4. Rules carried over

Verified or silent; help is visible as help (assisted, ADR 0005); every number has a denominator; uncertain detector results leave numerator and denominator; the LLM words checked facts only; monthly model budget stays.

## 5. Success bar (fixed before recruiting)

15 stranger testers after 5 friends, 2 weeks. **Go:** at least 8 finish the report and at least 5 return unprompted. **Change course:** fewer than 3 return, or most say they would not train. Record what each tester did, not what they said.

## 6. Open questions (not decided)

1. Real report time for 20 games on the public host; whether the host needs more CPU and what that costs.
2. Which Maia rating bands are supported at 500 to 1000.
3. Hand-check design and size for generated drills (the owner did not want another 30-position check).
4. How a tester reaches the report again without an account (a link containing the username is the simplest; confirm privacy is acceptable since Chess.com games are public).
5. What "convert" means in a convert-this-advantage game: win only, or also draw by the engine at some level.
6. Whether `draw` in the 227 / 149 / 71 counts needs a corrected result mapping.

7. Competitor scan with sources (H1) before any doc claims "no one does this".
8. Whether to change the detectors' "decided" limit (600 cp) so winning positions get a verdict; a new detector version, ADR and hand-check.
9. Loss map or conversion report as the test product (section 2b).

## 7. Audit: keep / park / cut (proposed; the owner decides each row)

| Area (ADR / task) | Proposal | Why |
|---|---|---|
| Evidence engine, `hanging_own` v4 (M1), `missed_free` v3 (M2), verifier | **Keep** | They produce every verified reason in the report. |
| Chess.com sync (T08) | **Keep** | The username entry needs it (extend to on-demand, public archives). |
| Drill library, timing classes, drill check (ADR 0017) | **Keep** | Public drill source; hand-check method reused for generated drills. |
| Play vs Stockfish, Practice, hints, threat warning (T06, T33 to T46) | **Keep** | Behind the website play option and convert-this-advantage game. |
| Maia-3 opponent (ADR 0012, 0016) | **Keep, check low bands** | Needed for play and for generated drills. |
| MCP connector and board (ADR 0007 to 0010) | **Keep** | The chat surface of the test. |
| Drill cycles (ADR 0018) | **Park** | Built, never run on a real bank; not in the test. |
| M3 missed threat (ADR 0011, 0013 to 0015) | **Park** | Failed hand-check; stays off. |
| Blind-spot map, baselines, real-game rate windows (T14 to T16, P2, P4b) | **Park** | Owner-only machinery; the conversion rate replaces the headline. Revisit for Door 2. |
| Delayed tests, Progress, Replay My Mistakes (P3, P4a) | **Park** | Needs accounts and history; after the bar is met. |
| Review tab, "what were you considering?" (T19), coach agent (T17), E2 evals | **Park** | Not needed for the test. |
| Peer benchmark, miss-likelihood model (T14b, T26, T27) | **Park** | Rating-scale caveats; not the first claim. |
| Practice bank from Lichess puzzles (T25) | **Cut (proposed)** | Replaced by own, public and generated drills. |
| Full opening book (T43), board upgrades (T29), Postgres (T30), CI (T23) | **Park** | CI (T23) is worth doing before strangers use it. |

## 8. Build order (once the owner approves this spec)

1. Measure report time and check Maia bands (answers open questions 1 and 2).
2. Conversion report service on existing evidence code.
3. One-page website: username, report, drills, play.
4. Convert-this-advantage game.
5. Generated drills and their hand-check.
6. ChatGPT smoke test; recruit 5 then 15.
