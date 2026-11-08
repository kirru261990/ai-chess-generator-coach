# Competitor set for the idea (draft, before the analysis)

Agreed by the owner on 2026-11-08 and analysed in `docs/competitive-analysis-2026-11-08.md`.

As-of 2026-11-08. This list says **who** to analyse and **why**, not how good they are. Evidence labels: **[F]** read on a page, **[V]** vendor claim only, **[S]** seen in a search result only, **[N]** named but not researched. It replaces the narrower set in `docs/competitive-analysis-2026-11-08.md`, which missed several overlapping products (for example Chessigma's "Chess DNA" and conversion diagnosis).

## The idea, as five jobs

| Job | What the player gets |
|---|---|
| J1 Diagnose | Where I lose games from my own games: phase, zone after move 5 (ahead / level / behind), conversion |
| J2 Train from my games | Drills built from my own mistakes, repeated, including from before my first slip |
| J3 Verified explanation | A "why" that an engine or detector checked; the language model only words it |
| J4 Prove it | A fixed baseline and a later result for my own games, including honest "no change" |
| J5 Reach people where they are | The same service in Claude and ChatGPT as well as a website |

Personal-first, the core is J1, J2, J4. J3 supports them. J5 comes later.

## Tier A: overlaps two or more jobs

| Competitor | Jobs it claims | Evidence | Researched |
|---|---|---|---|
| Chess.com (Insights, Game Review, Premium) | J1, part of J2, part of J4 ("Past Performance") | [F] support article 27 Jan 2026 | Yes |
| Aimchess (owned by Chess.com) | J1, J2 (Advantage Capitalization trainer, Blunder Preventer) | [F] vendor site; stale-looking | Yes |
| Chessigma | J1 and J2 ("Chess DNA", daily plan, blunder training, a conversion diagnosis), J3 ("Supercoach" coach chat), J5 (public API, agent skills and MCP documentation route) | [V] pricing page lists coach features as "coming soon" while the blog says live; only Chess.com games supported for the coach | Partly (own notes in `~/Documents/Codex/2026-10-12/.../public-product-research.md`) |
| Noctie | J2, J3 (post-game feedback, custom exercises), human-like practice partner | [S] listings only | No |
| LLM-explanation coaches: Chessiro Coach, Chessy, Chessful, Notation, ChessLine, Chessvia | J3, some J1 and J2 | [S] vendor and app-store pages; several state "the engine picks the move, the language model explains it" | No |
| Mistake-to-puzzle tools: Learn From Your Blunders, Chessie, ChessForge, Blind Spot Trainer (open source) | J2, some J1 | [V] Product Hunt pages | Partly |

## Tier B: one job, or adjacent

| Competitor | Job | Evidence | Researched |
|---|---|---|---|
| Decode Chess | J3 (explains Stockfish in words); free tier 1 game a day (third-party listing) | [S] | No |
| Lichess (Insights, Learn from your mistakes, Maia bots) | J1, J2 per game, free | [F] forum threads; Lichess pages returned 403 | Partly |
| Chessable (owned by Chess.com) | J2 through courses and spaced repetition | [N] | No |
| Chessreps | J2 for openings only: spaced repetition, lines from Lichess games, $34.99 a year (own notes); no plan built from your own games found | [F] own notes, [S] listings | Partly |
| Chessiverse, Chessmood | Practice opponents and courses | [S] | No |
| Human coaches, conversion courses ($80 to $300 in one search) | J1, J2 | [S] | No |
| Chess Tempo, Dr. Wolf, ChessBase and Fritz, Lucas Chess, ChessKid | Tactics, audio lessons, desktop analysis, kids | [N] | No |
| Chessbook | Not found in two searches | [N] | No |

## J5 distribution competitors (chess inside AI chat)

Chess Coach MCP (Lichess, Stockfish plus language model), ChessAgine MCP, Lichess MCP, Chess.com MCP (interactive views, ChatGPT and Claude), ChessMCP (play in ChatGPT with a board widget), Chessigma's MCP documentation route. All **[S]**, developer projects; none read in detail.

## Non-consumption (the real competitor for many players)

Free engine review with no training, posting a lost game in a forum for feedback, a human coach, and simply playing more.

## Gaps

Chessbook, Chess Tempo, Chessable, Noctie and Decode Chess were not read. Chessigma's claims about "conversion" and "Chess DNA" come from a 12 Oct 2026 note and are unverified here.
