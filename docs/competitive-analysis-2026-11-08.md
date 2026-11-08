# Competitive Analysis: tools that show chess players where they lose and train them

As-of 2026-11-08 · Owner: Karthik Raman · Redone after reading the sibling skills (the first version of this file, committed nowhere, did not use them).
Method: the six-step process in [competitive-analysis-process](https://github.com/deanpeters/Product-Manager-Skills/tree/cfcb697f14b8891d8b3ec43c16c3547df3e70e13/skills/competitive-analysis-process) and the skills it calls (landscape scan, research snapshot, voice-of-customer miner, positioning statement, intel watch, collection disciplines, autonomous investigation), all at commit `cfcb697`.
Builds on `docs/competitor-scan-2026-11-07.md`. Hypotheses come from ADR 0019, `docs/product-spec-v1.md` and `docs/personal-study-v1.md`.

**Labels:** **[F]** fact with a source and date, **[I]** inference (evidence plus a leap you can judge), **[A]** assumption. Things not found go in the gaps list, not under a label. Public information only; no product was trialled.

## Step 0: Scope

- **Decision:** what the owner builds and what the owner claims, for personal use first. Specifically: which parts of the plan already exist elsewhere (use), and which do not (build).
- **Hypotheses tested:** H1 nobody does conversion or tactics from your own games; H2 conversion is a big leak; H3 players want a report of their own games; H4 squandered advantages are tactical; "measured proof of improvement is an open angle"; "early collapse (first slips by move 5 to 6) is unserved".
- **Question budget:** 0 asked (the request carried the context).
- **Steps run:** 1, 2, 3, 5, 6, 7. **Step 4 skipped:** revenue and channels do not change a personal-first decision. **Battle card skipped:** no sales team. **Positioning statement:** run as a flagged hypothesis only (its own rules say not to use it for internal tools or before the problem is validated).
- **Do-not-invent list:** product features, prices, ratings, user counts, study results, competitor roadmaps, quotes. Everything below is from a page that was read, or is marked as a gap.

## Step 1: Landscape (market, in the buyer's words: "learn from my own games so I lose fewer of them")

**How buyers experience the market.** Not by vendor category. A player either uses what sits in the site where they play, pays a separate app, turns mistakes into puzzles, buys a course, or does nothing.

| Group | Players (max 12; strongest signal) | Evidence |
|---|---|---|
| Platform tools | Chess.com Insights, Game Review, Play Coach (Premium); Lichess "Learn from your mistakes" | [Chess.com Insights article, 27 Jan 2026](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com); [Chess.com membership](https://www.chess.com/membership) |
| Standalone analytics + training | Aimchess | [aimchess.com](https://aimchess.com) |
| Mistakes to puzzles | Learn From Your Blunders, Chessie, ChessForge | [Product Hunt](https://www.producthunt.com/products/learn-from-your-blunders), [Chessie](https://www.producthunt.com/p/chessie/chessie-2), [ChessForge](https://www.producthunt.com/p/chessforge) |
| Courses and coaches | Paid conversion courses, coach newsletters | [Chess Chatter](https://chesschatter.substack.com/p/convert-winning-positions) |
| **Non-consumption** | Free engine review with no training; posting a lost game on a forum for human feedback; a coach; just playing more | [Lichess thread](https://lichess.org/forum/game-analysis/problem-with-conversions) |

- **[F]** Aimchess was acquired by Play Magnus Group in 2021, and Chess.com acquired Play Magnus Group in December 2022 ([Play Magnus Group](https://playmagnusgroup.com/chess-training-and-analytics-startup-aimchess-joins-play-magnus-group), [Chess.com](https://www.chess.com/news/view/chesscom-acquires-pmg)). The App Store lists the developer as "Chess.com, LLC".
- **[I]** The biggest player owns the platform, the analytics, the course marketplace and the standalone app. Anything built on Chess.com game data depends on it.
- **Dynamics [F, weak]:** several small entrants launched in 2025 and 2026 (relative dates on Product Hunt); the pricing reference point is low ("$2/month or $15/year", a maker comment for Learn From Your Blunders).

**Whitespace, with the dead-zone test** (every claim gets an honest counter-reading):

| Whitespace claim | Counter-reading ("or is it a dead zone?") | Verdict |
|---|---|---|
| Measured proof that training changed *my* results, with a fixed baseline | Chess.com Insights already has "Past Performance" (last N days against the previous N) and accuracy over time [F]; no verbatim in this research asks for proof; players may use rating as the scoreboard [I] | **Narrow, possibly a dead zone commercially.** Valid for the owner's own purpose |
| Results by engine evaluation at a fixed early move (ahead / level / behind) | Closest are Chess.com "accuracy by move number" and Aimchess "Advantage capitalization", neither stated to bucket results by evaluation [F, vendor wording]. Demand for the *conversion* part is visible (Step 3) | **Partly open** |
| Start a drill one or two turns *before* the first mistake | One user asked for it on Lichess (Step 3); Lichess's feature starts at the mistake [F] | **Open, thin demand evidence** |

**So what.**
1. Conversion and "puzzles from your mistakes" are crowded; compete on neither.
2. Chess.com can ship any of this; build only what its incentives make unlikely (honest null results, fixed baselines).
3. Two deep-dive players: Chess.com Insights, Aimchess. The mistake-to-puzzle group is represented by Learn From Your Blunders.

## Step 2: Product-level comparison

Vendor claims below are facts about what the vendor *says*, not proof it works.

| | Chess.com (Insights, Game Review) | Aimchess | Learn From Your Blunders (as one of 3 similar) |
|---|---|---|---|
| Positioning | "Reveals patterns and statistics like your wins and losses, accuracy, common mistakes" | "Unique analytics with personalized lessons (created from your games!)" | "Chess puzzles based on your blunders" |
| Relevant capability | Insights: game phases, openings, moves, **tactics found vs missed (forks, pins, mates, hanging pieces)**, "Past Performance", "Similar Players" | Six aspects incl. **Advantage capitalization**, about 13 trainers incl. Blunder Preventer, Advantage Capitalization Trainer, Opening Improver | Analyses "openings, missed tactics, repetitive blunders, lost advantages" |
| Strength (likely) | Data and distribution; one place for games, review and lessons | Longest focus on personalised training; peer comparison "to others with the same rating" | Low price; focused on the mistake-to-puzzle loop |
| Weakness (likely) | Insights is Diamond-only [F]; complaint about usability for learning (Step 3) | App Store history shows no release since 06/28/2024 [F, snapshot date unknown]; effect claim without a linked study | 1 review (5.0); pricing from a maker comment; vendor site not read |
| Price (as found) | Not on the pages read; Insights needs Diamond | Web: free (one 40-game report a month), $7.99 a month, $57.99 a year; App Store: $9.99 a month, $71.99 a year (store pricing differs; reason not stated) | "$2/month or $15/year" (maker comment) |
| Key sources | Insights article, membership page | aimchess.com, App Store page | Product Hunt |
| **Evidence quality** | **Medium** (vendor support page, dated) | **Medium-low** (vendor page, copyright 2021, no dates) | **Low** (launch page, 1 review) |

**Capability checks against our plan** (what each *states*; "not stated" is not "absent"):

| Check | Chess.com | Aimchess | Mistake-to-puzzle group | Lichess |
|---|---|---|---|---|
| Own mistake rate over time vs an earlier period | **Partly yes** ("Past Performance", "accuracy over time", "Move quality over time") | Peer baseline, not own baseline; "My statistics page" (Premium) | Not stated | Not read (403) |
| Training effect measured | Headline "Increase Your Rating 2.7X Faster With Premium!", no method on the page | Claims "31% faster" with a footnote to a "12 week randomized field experiment" at UBC; **no link or outcome measure; I could not find the paper** | Not stated | Not read |
| Results split by evaluation at a fixed early move | No (closest: accuracy by move number) | Not stated | Not stated | Not read |

**Parity warning.** "Turns your mistakes into puzzles" and "finds your repeated patterns" appear on every tool in the group. The vendor claims "31% faster" (fetched page) and a "40% faster than peers" figure (seen in one search summary of the homepage) conflict; only the fetched wording is used here.

**[I] Build versus use:** Chess.com Insights already counts missed hanging pieces and shows change over time, so measuring M1 and M2 is partly available to a Diamond member. What it cannot offer is a fixed, pre-registered, versioned measure: the platform can change its definitions without notice, whereas ours are pinned (AGENTS rule 6) and hand-checked.

## Step 3: Voice of the customer

All quotes are verbatim, copied from the page text read on 2026-11-08. Source types and their skew are stated. This is discovery evidence, not a statistical method; every theme is a hypothesis to validate in interviews.

**Theme A: "Tell me why the move was wrong."** Frequency: recurring on one site (two threads, both Chess.com beginners section), old (2019 to 2021).
- "the descriptive text doesn't help me know WHY the suggested move is better" ([oneleftfoot, Chess.com forum, 13 Nov 2020](https://www.chess.com/forum/view/for-beginners/learning-why-a-move-is-a-mistake-blunder))
- "Is there anyway to find out why moves are rated the way they are?" ([pluviosilla, Chess.com forum, 5 Oct 2019](https://chess.com/forum/view/for-beginners/analysis-tells-me-a-move-is-excellent-good-inaccurate-or-a-blunder-but-why))
- Who says it: self-selected beginners who asked a question. Reading **[I]**: the need is an explanation, not another label. Counterpoint in the same thread: "Most times I make a mistake or blunder, I can usually understand why when I look at the analysis."

**Theme B: "Let me train on my mistakes across all games, from before the mistake."** Frequency: recurring on one site (two Lichess feature-request threads, undated).
- "I suggest setting up a way to go through your mistakes across ALL games for which the computer analysis has been run." ([eaglesdc, Lichess forum](https://lichess.org/forum/lichess-feedback/create-learn-from-your-mistakes-across-all-games))
- "instead of doing this on mistake turn, i wish you could start from one or two turns before" ([hal9k, Lichess forum](https://lichess.org/forum/lichess-feedback/love-learn-from-your-mistakes-can-it-be-implemented-to-use-all-my-games))
- Who says it: fans of the feature asking for more, not complaints. Reading **[I]**: supports the "before my first slip" drill kind and a cross-game review, as a request, not as proof people would pay.

**Theme C: "I get winning positions and lose them."** Frequency: recurring across two sites; a search for the topic returned more than ten further thread titles that were not read, so the count of threads is not a frequency.
- "I often lose games that I had a winning position in" ([tinaseiskaffee, Lichess forum](https://lichess.org/forum/game-analysis/problem-with-conversions))
- "I often get into clearly winning positions, but somehow still manage to lose or draw the game." ([youthap, Chess.com forum, Apr 2026](https://www.chess.com/forum/view/general/why-do-i-keep-losing-winning-positions))
- Who says it: players who chose to post. **The cause is contested across the three sources read:**
  - Lichess thread: a hanging rook ("33 Qb4? was your decisive mistake as your queen leaves Rd1 unprotected", tpr) and a rushed move after spending time.
  - Chess.com thread: "It's not always time trouble, and it's not always obvious blunders either." (youthap)
  - A coach's newsletter (commercial, sells a conversion course): "The harsh truth is that solving more tactics won't fix this problem." ([Dalton Perrine, Substack, 13 Jan 2026](https://chesschatter.substack.com/p/convert-winning-positions))
- Reading **[I]**: the need is real and widely reported; whether it is tactical is disputed.

**Theme D: "Insights are hard to turn into learning."** Frequency: isolated but vivid to recurring (two Chess.com threads, paying members).
- "it's just useless graphs I have to scroll through looking for something of value." ([KevinTheSnipe, Chess.com forum, 7 May 2024](https://www.chess.com/forum/view/site-feedback/better-insights))
- "but I'd ideally like to use them to learn." ([VelouriousFog, Chess.com forum, 20 Dec 2023](https://chess.com/forum/view/general/how-to-use-insights-to-improve))
- Who says it: paying customers asking for more value; skews negative.

**Competitor weak points (evidence quality in brackets):** Chess.com Insights, usability for learning [low: two threads]. Aimchess, stale-looking app and page [low: one store snapshot and a 2021 footer]. Aimchess and Chess.com, effect claims without a method [medium: the pages show the claim, the missing method is an absence]. Mistake-to-puzzle tools, quality unknown [no reviews to judge].

**Switching triggers.** None found. The threads show price complaints ("I pay the equivalent of about $15 a month", a favourable Aimchess blogger, 2023) but not a reason to leave one tool for another. **This is a gap.**

**Bias notes.** Forum posters self-select and over-represent confusion; feature-request threads come from fans; paid-feature feedback comes from paying members and complains about value; the Aimchess forum post is the developer's own; the Product Hunt page has no reviews; the Substack source is commercial. Reddit could not be read directly. Chess.com threads are mostly 2019 to 2021.

**So what.** Three opportunity hypotheses, phrased as problems: (1) players cannot tell *why* they keep losing positions they were winning; (2) players want to retrain from the moment before the first mistake, across games; (3) players with paid analytics cannot turn them into practice. Validate in 5 interviews before building anything for others (the skill's own handoff).

## Step 5: Perception and positioning

- **Promise-delivery gap [I]:** Chess.com's headline is "Increase Your Rating 2.7X Faster With Premium!" and Aimchess's is "31% faster", neither with a method on the page; users in the threads ask for the *why* and say the graphs don't help them learn.
- **Positioning statement (hypothesis only, not for sharing).** The skill says not to write one for internal tools or before the problem is validated, and the owner is the only user, so this is a note to self:
  - *For* recreational players who keep losing games they felt they should have won, *who need* to know whether training actually changes their own results, *a measurement-first training log* *that records a fixed baseline in advance and reports when nothing changed.* *Unlike* Chess.com Insights and Aimchess, *which* show trends and claim faster improvement without a method on the page.
  - Stress test: recognisable? **Unknown** (no one else asked). Defensible need? **Partly** (Theme D, but no one asked for proof). Believable differentiation? Yes, it is a stance (pre-registration, honest nulls), hard for a vendor selling improvement claims to adopt **[I]**. Guides decisions? Yes: no feature that cannot be measured. Not socialised.

## Step 6: Strategic direction (collection plan and fusion)

**Variables.** TARGET: Chess.com (including Aimchess) and the new mistake-to-puzzle entrants. MARKET: online chess instruction software (industry code not looked up). GEOGRAPHY: global. BUYER: recreational players rated 500 to 1600. CAPABILITY: personalised post-game analysis, training and measurement. DECISION: what the owner builds and claims. **Disciplines run (2 to 3, as the playbook requires):** OSINT (news, blogs, support pages), SIGINT (app-store history, pricing and product pages), HUMINT (hiring; failed, see gaps).

| Discipline | Signal | Label | Source and date |
|---|---|---|---|
| OSINT | Insights article describes "Past Performance", tactics found vs missed (hanging pieces) | Fact | [Chess.com support, 27 Jan 2026](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com) |
| OSINT | Chess.com news pages 1 and 2 (16 Oct to 7 Nov 2026) have no post about Insights, Game Review, coach or training | Fact (absence, two pages only) | [Chess.com news](https://www.chess.com/news) |
| OSINT | Lichess blog 2026: no dedicated insights or learning feature post; mobile update 24 Mar 2026 mentions "learn from mistakes" in image alt text | Fact, weak | [Lichess blog](https://lichess.org/blog) |
| SIGINT | Aimchess App Store: latest version 1.3.1, 06/28/2024; snapshot date not shown | Fact, weak | [App Store](https://apps.apple.com/us/app/aimchess-learn-chess-online/id1524941307) |
| SIGINT | Aimchess site footer "Copyright © 2021"; blog page returned no posts | Fact, weak | [aimchess.com](https://aimchess.com) |
| SIGINT | Membership page lists Unlimited Game Review, Play Coach, Unlimited Puzzles; no prices in the text read | Fact | [Chess.com membership](https://www.chess.com/membership) |
| OSINT | Three mistake-to-puzzle tools launched on Product Hunt (2025 and 2026 by relative dates) | Fact, weak | Product Hunt pages above |
| HUMINT | Chess.com jobs page did not render roles | Gap | [Chess.com jobs](https://www.chess.com/jobs) |

**Stacking rule applied (one channel = watch, two = working hypothesis, three or more = actionable, conflict = dig):**
- *Chess.com extends in-platform analytics:* one clear channel (support article) plus a negative on news = **watch**.
- *Aimchess is winding down:* two weak signals from the same vendor surface (store history, site footer) = **watch, not a working hypothesis**; not corroborated by hiring or news. An announcement would be treated as intent only; none was found.
- *More entrants:* weak, relative dates = **watch**.
- **Verdict: monitor. No action trigger.** The earlier "Chess.com Play Coach and celebrity coaches" signal is undated in what I read and is practice for beginners, not analysis; not used.

## Step 7: Outputs

| Output | Built? | Consumer | Fed by |
|---|---|---|---|
| Comparison matrix | Yes (Step 2) | Owner | 2 |
| Positioning counter-move | Hypothesis only (Step 5) | Owner | 3, 5 |
| Threat assessment | Yes (Step 6: monitor) | Owner | 6 |
| Battle card | Skipped | n/a | n/a |

**Hypothesis verdicts**

| # | Hypothesis | Verdict now | Change from the first pass |
|---|---|---|---|
| H1 | Nobody does conversion or tactics from your own games | **Refuted** (Aimchess has an Advantage Capitalization trainer and analytics aspect; Chess.com Insights counts missed hanging pieces) | Stronger |
| H2 | Conversion is a big leak | Widely reported by players (Theme C); our data: 25% of losses start ahead | Unchanged |
| H3 | Players want a report of their own games | **Partly supported**: demand for *why*, *across games*, *from before the mistake*, *conversion*; no evidence yet for a new tool or willingness to pay | Narrower |
| H4 | Squandered advantages are tactical | **Contested**: sources split between hanging pieces, not-obvious blunders, and technique | **Downgraded** from "weakly supported" |
| Open angle | Measured proof of improvement | **Narrowed**: Chess.com has over-time views; an Aimchess effect claim has no link; a fixed pre-registered baseline was not found; possibly a commercial dead zone, valid for the owner | Narrowed |
| Early collapse | Start from before the first slip | **Thin demand evidence** (one request); not found as a product | Slightly stronger |

**Build versus use (decision).** Use first: try the Chess.com Diamond trial for Insights and one free Aimchess report on the owner's account, and compare with our loss map. Build only what stays unserved and cheap: the pre-registered, versioned measurement, and the "before my first slip" drill after a hand-check. Do not rebuild the mistake-to-puzzle loop or the conversion replay.

**Maintenance cadence (baseline for the intel watch).** This document is the baseline snapshot. Re-run only the delta quarterly and before any decision to share the product. Materiality bar: report a change only if it would change what the owner builds or claims. Watchlist: Chess.com Insights or Game Review changes; any tool that reports mistake rates against a fixed baseline; Aimchess store and web activity; the Aimchess study behind "31% faster". Not installed as a schedule.

## Gaps list

- Lichess Insights and Learn-from-your-mistakes pages returned 403; only forum threads and secondary sources were read for Lichess.
- Chess.com membership prices and free-tier limits were not on the page text; Chess.com job roles did not render; Chess.com news page 3 and older were not read.
- The Aimchess UBC study could not be found; the vendor's effect claim is unverified.
- Google Play listing for Aimchess not checked; the App Store snapshot has no fetch date.
- Chessie, ChessForge and Learn From Your Blunders vendor sites were not read; their pricing and quality are unverified.
- Reddit was not reached directly; more than ten "losing winning positions" threads appeared in search results but were not read.
- No data on switching triggers, willingness to pay, or conversion of any competitor.
- The Theme A quotes are from 2019 and 2020 and may not reflect current products; the Lichess quotes in Theme B and the Lichess conversion thread are undated.

## Final step: what next (pick one)

1. **Try the two free checks:** Chess.com Diamond trial (Insights) and one free Aimchess report on the owner's account, then compare with our loss map.
2. **Validate the three problem hypotheses:** five short interviews with players rated 500 to 1600 before anything is built for others.
3. **Install the watch:** quarterly delta on this baseline, with the watchlist above.
4. **Update ADR 0019, the spec and the study plan** with these verdicts.
