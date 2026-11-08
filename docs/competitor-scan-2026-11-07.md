# Competitor scan, 2026-11-07 (time-boxed, web search only)

Question (ADR 0019 H1): does anything already show a player where they lose games, and train them from their own games? Method: five web searches, summaries read, no product trialled. Vendor pages and forum posts are unverified; features and prices may have changed.

| Tool | What it does (as found) | Source |
|---|---|---|
| Chess.com Insights | Looks at all your games; tactics section, openings section, accuracy by game phase. Described as a Diamond-members feature. | [support article](https://support.chess.com/en/articles/8708925-what-is-insights-on-chess-com), [launch post](https://chess.com/news/view/chesscom-releases-new-insights-feature) |
| Lichess Insights | Indexes your games with phase detection, material imbalances, move times and more. Only for games on Lichess. Official description not found; secondary sources only. | [Lichess blog](https://lichess.org/blog/VmZbaigAABACtXQC/chess-insights) |
| Lichess "Learn from your mistakes" | Walks through the errors in a game; later update says players can train tactics missed in their own games. Needs computer analysis; per game, not across all games. | [Lichess blog](https://lichess.org/blog/WFvLpiQAACMA8e9D/learn-from-your-mistakes) |
| Aimchess | Analyses recent games; adaptive tactics puzzles; **replay games you lost despite a significant advantage**; opening improver with spaced repetition. Free tier 3 reports of 40 games; paid about $7.99 a month. One review site suggests maintenance mode (unverified; last App Store update found June 2024). | [aimchess.com](https://aimchess.com), [App Store](https://apps.apple.com/us/app/aimchess-learn-chess-online/id1524941307?uo=4) |
| Learn From Your Blunders, Chessie, ChessForge, BlunderLab, Blind Spot Trainer (open source) | Turn your mistakes into puzzles or find repeated patterns; Learn From Your Blunders lists "lost advantages". All vendor or launch pages, none verified. | [Product Hunt](https://www.producthunt.com/products/learn-from-your-blunders), [Chessiro comparison](https://chessiro.com/blog/best-chess-analysis-tools) (written by a vendor) |
| Conversion courses | Many human-made courses on converting an advantage (about $80 to $300, 4 to 16+ hours). | [Golichenko course](https://thechessworld.com/store/product/converting-advantage-into-a-win-with-im-illia-golichenko/), [KnightMaster](https://knight-master.com/grandmaster-chess-courses/chess-strategies-to-convert-winning-positions) |

## What this means

- **H1 is refuted for conversion and for "tactics from your own games".** Aimchess has a conversion replay, several tools build puzzles from your mistakes, and courses on converting advantages are common. "Nobody focuses on this" must not appear in any doc.
- **Not found in this scan** (not searched for directly, so absence is not proof): a tool that sets a baseline on your real games, trains, and then reports whether your mistake rates fell, with denominators. That is the one angle the project already builds (PRD v2: frozen baseline window, 72-hour delayed tests, real-game rates with floors).
- **Build versus use, for the owner:** the loss-by-zone view (ahead / level / behind after move 10) was not found in any listed tool, but Chess.com Insights' phase accuracy is close. Cheapest check: run one free Aimchess report on the Chess.com account and look at Chess.com Insights, then compare with `docs/decisions/0019-middlegame-conversion-pivot.md`.
- **Limits:** five searches; no product was used; ChessBase, Chessable and other paid platforms were not searched.
