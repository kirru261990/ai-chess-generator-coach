# Competitive Analysis: tools that show chess players where they lose and train them

As-of 2026-11-08 · Owner: Karthik Raman · Second full pass, on the competitor set agreed in `docs/competitor-set-2026-11-08.md` (the first pass covered only Chess.com and Aimchess).
Method: the six-step process in [competitive-analysis-process](https://github.com/deanpeters/Product-Manager-Skills/tree/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/skills/competitive-analysis-process) and the skills it calls, at commit `cfcb697`. Hypotheses from ADR 0019, `docs/product-spec-v1.md`, `docs/personal-study-v1.md`.

**Labels:** **[F]** fact read on a page, with source; **[V]** vendor claim (a fact about what the vendor says, not proof it works); **[I]** inference; **[A]** assumption. Things not found go in the gaps list. Public pages only; no product was trialled; most vendor pages carry no date.

## Step 0: Scope

- **Decision:** what the owner builds and claims, personal-first. Which of the five jobs already exist elsewhere (use), and which do not (build).
- **Jobs:** J1 diagnose where I lose; J2 train from my own games; J3 verified explanation; J4 prove it (fixed baseline, later result); J5 reach people inside Claude and ChatGPT as well as a website. Core for the personal study: J1, J2, J4.
- **Set analysed (agreed):** Chess.com, Aimchess, Chessigma, Noctie, Decode Chess, the "Stockfish plus language model" coaches (Chessiro as the lead, with Chessy, Chessful, ChessLine, Notation, ChessCoach), the mistake-to-puzzle cluster, chess MCP servers (J5 only), and Chessreps and Chessable as adjacent notes.
- **Steps run:** 1, 2, 3, 5, 6, 7. **Skipped:** Step 4 (revenue and channels do not change a personal-first decision) and the battle card (no sales team). The positioning statement is a flagged hypothesis only.
- **Do-not-invent list:** features, prices, ratings, user counts, study results, roadmaps, quotes. Everything below comes from a page that was read or is in the gaps list.

## Step 1: Landscape

**How buyers experience the market:** by what they do after a game. They paste it into a free engine, open the platform's own review, pay a coach app, turn mistakes into puzzles, drill openings, buy a course, or ask a forum.

| Group | Players | Closest to |
|---|---|---|
| Platform tools | Chess.com Insights and Game Review; Lichess | J1, part of J2 and J4 |
| Standalone analytics + training | Aimchess; **Chessigma** | J1, J2 |
| Stockfish plus language-model coaches | Chessiro, Chessy, Chessful, ChessLine, Notation, ChessCoach, Noctie, Decode Chess | J3, some J1 and J2 |
| Mistakes to puzzles | Learn From Your Blunders, Chessie, ChessForge | J2 |
| Openings and courses | Chessreps, Chessable, conversion courses | adjacent |
| Chess inside AI chat | Chess-com MCP, Chess Coach Agent, others | J5 |
| **Non-consumption** | Free engine review, forum feedback, a human coach, playing more | all |

- **[F]** Chess.com owns the platform, Insights, Aimchess and Chessable's parent: Aimchess was bought by Play Magnus Group in 2021 and Chess.com bought Play Magnus Group in December 2022 ([Play Magnus Group](https://playmagnusgroup.com/chess-training-and-analytics-startup-aimchess-joins-play-magnus-group), [Chess.com](https://www.chess.com/news/view/chesscom-acquires-pmg)).
- **[F]** Price points seen: $2.99 to $14 a month, with one-off or lifetime options common (Notation £6.99 once; Chessful $29.99 lifetime; Chessy $79.99 lifetime; Chessigma $490 lifetime). **[I]** Price pressure is high; a paid product here would be hard to sustain, which matches the project's "no revenue now" stance.

**Whitespace with the dead-zone test:**

| Claim | Counter-reading ("or is it a dead zone?") | Verdict |
|---|---|---|
| Measured proof that training changed my results, fixed baseline, honest nulls | Every vendor claims an effect (see Step 2) and users appear to accept claims; no verbatim read asks for proof; Chess.com Insights has "Past Performance" | **Possibly a dead zone commercially; valid for the owner's purpose** |
| Explanations checked against the engine, with published accuracy | Notation, Chessiro and Decode Chess already claim engine grounding; users praise getting the "why" (Step 3) but none asked for verified accuracy | **Weak differentiator**; keep it as an engineering rule |
| Results by evaluation at a fixed early move (ahead / level / behind) | Chessigma and Aimchess describe conversion or "advantage capitalization" analytics; none stated to bucket results by an early evaluation | **Partly open** |
| Start a drill from before the first slip | One Lichess user asked for it; no product found doing it, but Chessigma's blunder training is "positions where you were about to hang something" | **Open, thin demand** |

## Step 2: Product-level comparison

**Closest competitor: Chessigma [V unless noted].** Its pages describe a five-area "Chess DNA" report (blunders, tactics, the clock, converting winning positions, openings), a daily plan "built every morning from your recent games" using up to 12 months of games, blunder training cut from your own games, a "Conversion Trainer" in the navigation, an AI "Supercoach" with chat (announced as open in an 8 Jul 2025 blog post), import from Chess.com, Lichess and PGN, and a public API with MCP documentation (own 12 Oct note). Prices as shown: $14 a month, $97 a year, $490 lifetime. Observations that lower confidence: the Endgame Trainer and Courses are marked "Soon" [F]; the headline "Our players gain +112 Elo in their first month" sits beside named examples of +191 to +232, with no method; the engine is described as Stockfish 16 in one article and 17 in its title; Trustpilot shows 3 reviews (3.6 average). Whether the coach's prose comes from a language model is not stated.

**Comparison of those with the largest overlap** (what each *states*; "not stated" is not "absent"):

| | Chess.com Insights | Aimchess | Chessigma | Chessiro | Notation | Chessy | Noctie | Decode Chess |
|---|---|---|---|---|---|---|---|---|
| Own-game diagnosis across games | Yes (phases, tactics, openings) | Yes (6 aspects incl. Advantage capitalization) | Yes (Chess DNA, 5 areas) | Claimed ("tracks the mistakes you repeat across games") | Claimed ("spots the patterns in how you play") | Yes (insights, weekly report) | Per game only | Per game; a testimonial mentions all games |
| Training from own mistakes | Separate tools | Yes (13 trainers) | Yes (blunder training, daily plan) | Yes (Replay Mistakes, Smart Shuffle) | Sparring partner, no drill generator | Yes (puzzles from your games) | Yes (decks from mistakes) | Not stated |
| Engine check on the "why" | n/a | not stated | "Stockfish supplies the ground truth" (own roundup) | "Every explanation starts from Stockfish 19"; self-reported 75 to 80% right | **"The LLM… never evaluates… That's why it doesn't hallucinate"** (no test cited) | Not stated | Grades "judged like a human, not an engine" | "Backed by a strong chess engine"; "every suggested concept is verified" |
| Price (as shown) | Diamond | Free (one 40-game report a month), $7.99 a month, $57.99 a year (App Store $9.99 / $71.99) | $14 a month, $97 a year, $490 once | Free (limited), ₹449 / ₹699 a month | £6.99 once (£2.99 launch) | $7.99 a month, $49.99 a year, $79.99 once | €14 a month, €96 a year, no free tier | Free (1 game a day), $8.25 a month, $84 a year |
| Recency signal | Article 27 Jan 2026 | App Store last release 06/28/2024 | Reviews to Jul 2026; blog to Aug 2026 | Blog 19 Jul 2026 | Page undated | Releases 4 Oct, 6 Oct, 22 Oct, 27 Oct, latest "15h ago" | Product Hunt 2024; © 2021-2026 | Footer 2022 |
| **Evidence quality** | Medium | Medium-low | Medium-low | Low (vendor ranks itself) | Low | Medium (store history) | Low | Low |

**Three more on the app-store side [V and F]:** Chessful (Stockfish on device, 10 mistake types, from $2.99 a month; latest 2.1.1 "1d ago"); ChessLine (opening deviations, 4.4 from 8 ratings; latest 1.2.2, 8 Oct); ChessCoach (Chrome extension reading the last 20 games, $9.99 a month; its page said the store launch was due June 2026, unconfirmed). Mistake-to-puzzle cluster (Learn From Your Blunders $2 a month per a maker comment; Chessie; ChessForge free plan): vendor pages, 0 to 1 reviews.

**Capability checks against our plan** (all three are "not stated" for almost everyone):

| Check | Result |
|---|---|
| Own mistake rate over time against an earlier period | Chess.com Insights partly yes ("Past Performance", accuracy and move quality over time). Chessigma "improvement trends" in image alt text, no baseline described. Everyone else not stated |
| Measured training effect | **No method anywhere.** Claims: Chess.com "2.7X faster"; Aimchess "31% faster" with an unlinked UBC footnote; Chessigma "+112 Elo in the first month"; Chessiro "of 108 players we measured, 83% are rated higher than when they joined"; ChessCoach "+180 in 8 weeks*" marked illustrative |
| Results by evaluation at a fixed early move | Not stated by any |

**Adjacent:** Chessreps trains openings with spaced repetition, courses checked against Lichess game data, $34.99 a year, own games not shown [F]; Chessable sells courses with spaced repetition, own games not shown, pricing not on the page read [F].

**J5, chess inside AI chat [F]:** Chess-com MCP runs in ChatGPT and Claude with interactive board views but only fetches a player's last game and the daily puzzle; no engine; Glama marks it "Inactive". "Chess Coach Agent" is a course-assignment repo, one finished Lichess game at a time, needs local Stockfish and Obsidian, 0 stars, Glama "Stale". Two others (Lichess MCP, ChessAgine MCP) returned 403. **[I]** No product found offers cross-game diagnosis or training inside ChatGPT or Claude; Chessigma's MCP documentation route is the only commercial signal.

**Parity warning:** "turns your mistakes into puzzles" and "finds your repeated patterns" are on almost every product.

**[I] Build versus use:** for J1 and J2, assume Chessigma, Aimchess, Chessy and Chess.com already do most of it. Test that by using them on the owner's account before building more.

## Step 3: Voice of the customer

Verbatim quotes, copied from the page text on 2026-11-08, with source type and bias. Hypotheses, not verdicts; frequency is stated honestly; Reddit was not reached directly.

**Theme A: "Tell me why."** Recurring (four threads and listings, two sites, 2019 to 2026).
- "the descriptive text doesn't help me know WHY the suggested move is better" ([Chess.com forum, 13 Nov 2020](https://www.chess.com/forum/view/for-beginners/learning-why-a-move-is-a-mistake-blunder))
- "Is there anyway to find out why moves are rated the way they are?" ([Chess.com forum, 5 Oct 2019](https://chess.com/forum/view/for-beginners/analysis-tells-me-a-move-is-excellent-good-inaccurate-or-a-blunder-but-why))
- "this is the first one that actually shows why I’m losing instead of just throwing stats at me." ([App Store review of Chessy, 16 Apr, year not printed](https://apps.apple.com/us/app/-/id6761496636))
- Bias: forum askers self-select; app-store reviewers skew to extremes. Reading **[I]**: demand for the *why* persists, and Chessy's review shows it is being met by at least one new product.

**Theme B: "Across all games, from before the mistake."** Two Lichess feature-request threads (fans asking for more).
- "I suggest setting up a way to go through your mistakes across ALL games for which the computer analysis has been run." ([Lichess forum](https://lichess.org/forum/lichess-feedback/create-learn-from-your-mistakes-across-all-games))
- "instead of doing this on mistake turn, i wish you could start from one or two turns before" ([Lichess forum](https://lichess.org/forum/lichess-feedback/love-learn-from-your-mistakes-can-it-be-implemented-to-use-all-my-games))

**Theme C: "I get winning positions and lose them."** Recurring on two sites; the cause is contested.
- "I often lose games that I had a winning position in" ([Lichess forum](https://lichess.org/forum/game-analysis/problem-with-conversions))
- "It’s not always time trouble, and it’s not always obvious blunders either." ([Chess.com forum, Apr 2026](https://www.chess.com/forum/view/general/why-do-i-keep-losing-winning-positions))
- "The harsh truth is that solving more tactics won't fix this problem." ([Chess Chatter, 13 Jan 2026](https://chesschatter.substack.com/p/convert-winning-positions); a coach who sells a course)
- A Lichess commenter blames a hanging rook ("33 Qb4? was your decisive mistake as your queen leaves Rd1 unprotected").

**Theme D: "Analytics don't help me learn" and "this app is not worth it."** Isolated to recurring, paying or app-store users.
- "it's just useless graphs I have to scroll through looking for something of value." ([Chess.com forum, 7 May 2024](https://www.chess.com/forum/view/site-feedback/better-insights))
- "You’re better off doing a lichess study than downloading this app." ([App Store review of ChessLine, 9 Sep, year not printed](https://apps.apple.com/app/id6748459144))
- "It's so greedy: filled with ads and sometimes force you to watch one when you do a game review" ([Trustpilot, Chessigma, 1 star, 12 Mar 2026](https://www.trustpilot.com/reviews/69b2208860f96946d2c9cdba))

**Competitor weak points:** Chessigma, unexplained headline claim and "Soon" items [medium]; Aimchess, stale-looking app and unlinked study [low]; Chess.com Insights, usability for learning [low]; several coaches, accuracy self-reported with no method [medium]; mistake-to-puzzle tools, unreviewed [no evidence].
**Switching triggers:** none found, beyond price complaints and ads. **Gap.**
**So what.** Opportunity hypotheses: (1) players cannot tell why they keep losing won positions, and experts disagree on the cause; (2) players want to train from before the mistake, across games; (3) paid analytics don't turn into practice. Validate with five interviews before building anything for others. The sample here is small: three Trustpilot reviews for Chessigma, 19 and 8 App Store ratings for Chessy and ChessLine.

## Step 5: Perception and positioning

- **Promise-delivery gap [I]:** every product promises faster improvement; none shows a method. Players ask for the *why* and for practice that fits their own games.
- **Positioning statement (hypothesis for the owner's own use, not for sharing; the skill advises against one before the problem is validated):** *For* recreational players who keep losing games they felt they should have won, *who need* to know whether training changes their own results, *a measurement-first training log* *that fixes its baseline in advance and reports when nothing changed.* *Unlike* Chessigma, Aimchess, Chessiro and Chess.com, *which* claim faster improvement without a method on the page.
- **Stress test:** recognisable? Unknown. Defensible need? Partly (nobody read asked for proof). Believable and falsifiable? Yes. Hard to copy in six months? Probably, since vendors selling improvement claims have little incentive to publish nulls **[I]**.

## Step 6: Strategic direction (collection plan and fusion)

**Variables.** TARGET: the Stockfish-plus-language-model coach segment, plus Chess.com. MARKET: online chess instruction software (industry code not looked up). GEOGRAPHY: global. BUYER: recreational players 500 to 1600. CAPABILITY: personalised analysis, training and measurement. DECISION: what the owner builds and claims. **Disciplines (2 to 3):** OSINT (launch pages, blogs, support articles, Trustpilot), SIGINT (app-store version history, pricing and product pages), HUMINT (Chess.com jobs page; did not render).

| Discipline | Signal | Label | Source and date |
|---|---|---|---|
| SIGINT | Chessy: five releases 4 Oct to 27 Oct, latest "15h ago"; Chessful 2.1.1 "1d ago"; ChessLine 1.2.2 on 8 Oct | Fact | App Store pages |
| OSINT | At least six Stockfish-plus-language-model coach apps are listed in 2026 roundups; Chessiro's roundup updated 19 Jul 2026 | Fact (vendor-written) | [Chessiro](https://chessiro.com/blog/best-chess-analysis-tools) |
| OSINT | Chessigma coach blog 8 Jul 2025; newest dated Chessigma page 15 Aug 2026; Trustpilot reviews to 19 Jul 2026 | Fact | Chessigma, Trustpilot |
| OSINT | Chess.com news pages 1 and 2 (16 Oct to 7 Nov 2026) have no analysis or training product post; Insights article dated 27 Jan 2026 | Fact (absence on two pages) | Chess.com |
| SIGINT | Aimchess App Store: last release 06/28/2024; site footer 2021 | Fact, weak | App Store, aimchess.com |
| OSINT | Glama marks Chess-com MCP "Inactive" and Chess Coach Agent "Stale" | Fact | Glama |
| HUMINT | Chess.com jobs page did not render | Gap | |

**Stacking rule (1 watch, 2 working hypothesis, 3 or more actionable, conflict = dig):**
- *The personalised AI-coach segment is crowded and fast-moving:* three channels (store release cadence, 2026 launch and roundup pages, review dates) = **actionable**. The action is to **not enter as a commercial coach**, and keep the project measurement-first and personal.
- *Chess.com extends in-platform analytics:* one clear channel plus a negative on news = **watch**.
- *Aimchess winding down:* two weak signals from one vendor surface = **watch**.
- *Chess inside AI chat is an open lane for analysis:* store and registry signals show only hobbyist, inactive projects = **working hypothesis**, not corroborated by hiring or funding.
- **Verdict:** threat to a commercial coach: **high**. Threat to the personal study: **low**. Review quarterly.

## Step 7: Outputs

| Output | Built? | Consumer | Fed by |
|---|---|---|---|
| Comparison matrix | Yes (Step 2) | Owner | 2 |
| Positioning counter-move | Hypothesis only (Step 5) | Owner | 3, 5 |
| Threat assessment | Yes (Step 6) | Owner | 6 |
| Battle card | Skipped | n/a | n/a |

**Hypothesis verdicts**

| # | Hypothesis | Verdict now |
|---|---|---|
| H1 | Nobody does conversion or tactics from your own games | **Refuted.** Chessigma, Aimchess, Chess.com, Chessy and others do |
| H2 | Conversion is a big leak | Widely reported by players; our data: 25% of losses start ahead at the checkpoint |
| H3 | Players want a report of their own games | **Partly supported**; the demand is for the *why*, cross-game training and conversion; products already meet it; willingness to pay for a new tool is not shown |
| H4 | Squandered advantages are tactical | **Contested** between hanging pieces, subtler errors and technique |
| J3 | Verified explanations are a differentiator | **Weak**: Notation, Chessiro and Decode Chess claim it; none cites a test. Our own evaluation (E2 v2, 110 of 110 on a frozen set, with caveats) is a point in our favour that no player has asked for |
| J4 | Measured proof of improvement is open | **Narrowed**: everyone claims, nobody shows a method; possibly a dead zone commercially; valid for the owner |
| J5 | Chess inside ChatGPT and Claude | **Open but hobbyist**: no product found offers cross-game diagnosis or training there |
| Early collapse | Start from before the first slip | **Thin demand**; no product found doing exactly this |

**Build versus use (decision).** Use first: try Chessigma's free analysis, one Aimchess report, Chessy's free tier and the Chess.com Diamond trial on the owner's own account, and compare each with our loss map. Build only what stays unserved and cheap: the pre-registered, versioned measurement (J4) and the "before my first slip" drill after a hand-check. Do not rebuild the mistake-to-puzzle loop, the conversion trainer or a commercial coach.

**Maintenance cadence (baseline for the intel watch).** This document is the baseline. Re-run only the delta quarterly and before any decision to share the product. Materiality bar: a change that would alter what the owner builds or claims. Watchlist: Chessigma (coach status, "Soon" items, conversion trainer, MCP); Chessy and Chessful release notes; Chess.com Insights; any product that reports mistake rates against a fixed baseline; the Aimchess study. Not installed as a schedule.

## Gaps list

- Lichess Insights and Learn-from-your-mistakes pages (403); the Lichess MCP and ChessAgine MCP pages (403); Chessable's about and Pro pages did not render; Chess.com membership prices, job roles and news beyond page 2.
- Chessigma Google Play listing (truncated), its Conversion Trainer page, which pricing column holds Chess DNA, and whether the coach text comes from a language model.
- Noctie: Product Hunt review text; independent reviews. Decode Chess: independent reviews; footer dated 2022.
- The Aimchess UBC study; any method behind Chessiro's "83% rated higher", Chessigma's "+112 Elo" or Chess.com's "2.7X".
- Chessiro has no App Store listing seen; Notation's App Store page not read; ChessCoach store status unknown.
- No data on switching triggers or willingness to pay; Reddit not reached; Chessbook not found; Chess Tempo, Dr. Wolf, ChessBase, Chessmood and Chessiverse not researched.
- No product was trialled; every feature claim is vendor wording.

## Final step: what next (pick one)

1. **Try the free tiers on the owner's account** (Chessigma, Aimchess, Chessy, Chess.com trial) and compare with our loss map; the owner signs in, I read the outputs.
2. **Validate the three problem hypotheses** with five short interviews of players rated 500 to 1600.
3. **Install the quarterly watch** on this baseline.
4. **Update ADR 0019, the spec and the study plan** with these verdicts.
