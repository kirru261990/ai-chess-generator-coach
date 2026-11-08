# Open-source survey: what others have built, and what we can reuse

As-of 2026-11-08. Extends ADR 0001 (approved data, engines and libraries), which already covers Lichess data, Stockfish, Maia, python-chess, chessground and the reference apps. This file covers whole projects found on GitHub.

**How to read it.** Facts come from each repo's GitHub main page, read on 2026-11-08. Licences are the GitHub sidebar entry, not the LICENSE file. Latest-commit dates and primary languages were not shown on any page; "not shown" is not "stale". README statements are vendor-style claims (**[README]**). This repo is AGPL-3.0-or-later, so GPL, AGPL, MIT, Apache and CC0 code can be combined with it; a repo with **no licence** cannot be copied. Rule from AGENTS.md: a `THIRD_PARTY.md` row comes before any new dependency. Nothing was run or tested.

## Closest to our idea

| Repo | Licence | Signal | What it does [README] | Reuse verdict |
|---|---|---|---|---|
| [deven1003/chess-coach-mcp](https://github.com/deven1003/chess-coach-mcp) | MIT (but **source is private**: "a showcase… access on request") | 0 stars, 1 commit on the shown branch | MCP server: recent games from Lichess and Chess.com, Stockfish depth 14, loss bands (blunder over 300 cp, mistake 100 to 300, inaccuracy 50 to 100), suspicious moves rechecked at depth 18, tools `get_recent_games`, `analyze_game`, `find_blunders`, `get_opening_stats`, prompts `coach_my_last_game` and `weekly_review`; "The server never explains anything" (the model does); motif tagging and puzzles are listed as roadmap | **No code to reuse.** Confirms the design is easy to reach (a direct J5 competitor). Our difference: tools return verified claims and are tested |
| [brianch/lichess-puzzler](https://github.com/brianch/lichess-puzzler) | MIT per sidebar, but it is a fork of a fork of an AGPL-3.0 generator | 0 stars, 472 commits | Generates puzzles from your own unanalysed PGN; CSV export compatible with Lichess puzzle readers | **Reference only until the licence chain is checked.** Same method as the next row |
| [ornicar/lichess-puzzler](https://github.com/ornicar/lichess-puzzler) | AGPL-3.0; the files read have no "or later" header (see the licence check below) | 180 stars, 50 forks | The generator, a theme tagger and a human validator used for the Lichess puzzle collection | **Study the method, do not copy code** (candidate selection, unique-answer checks, theme tags) |
| [JamarTG/litrainer](https://github.com/JamarTG/litrainer) | **None shown** | 24 stars, React + TypeScript | Turns your Lichess games into puzzles, Stockfish 17, per game, needs Lichess computer analysis | **Do not copy.** Product reference for the "mistake to puzzle" UX |
| [ai-chess-training/LLM-ChessCoach](https://github.com/ai-chess-training/LLM-ChessCoach) | MIT | 7 stars, has tests | FastAPI + Stockfish MultiPV + an LLM coach with a rule-based fallback; needs an LLM API key; docs name two different models | **Idea only** (rule-based fallback). Needs a paid key, which cuts against the bring-your-own-subscription idea |

## Building blocks worth using

| Repo / data | Licence | Signal | Use for |
|---|---|---|---|
| [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings) | CC0-1.0 | 587 stars | **Name the opening where a slip happened** and replace the 60-line starter list (task T43). Needs the owner's OK to download a small file and a `THIRD_PARTY.md` row |
| [CSSLab/maia3](https://github.com/CSSLab/maia3) | AGPL-3.0 | 214 stars | Already used (ADR 0012). Maia-2's README says Maia-3 is recommended for new projects |
| [CSSLab/maia2](https://github.com/CSSLab/maia2) | MIT | 162 stars | Older; keep only as a fallback |
| FSRS scheduling (via a library such as `ts-fsrs`, which Chessstack uses) | **not checked** | n/a | Schedule review of first-slip drills. A library licence must be checked before use |
| [PvtTwinkle/Chessstack](https://github.com/PvtTwinkle/Chessstack) | AGPL-3.0-or-later | 10 stars, tests, Docker | Closest in spirit to our J2 for **openings**: FSRS drills, "trouble spots", game review. Reference for the review screen and scheduling; compatible licence, small project |
| [ArneVogel/listudy](https://github.com/ArneVogel/listudy) | AGPL-3.0 | 403 stars, Elixir | Training UX reference (openings, tactics, endgames with spaced repetition); different stack |
| [GuillaumeSD/Chesskit](https://github.com/GuillaumeSD/Chesskit) | AGPL-3.0 | 433 stars, Next.js | Review screen and move-classification reference (already in ADR 0001) |
| [LinkAnJarad/OpenChess-Insights](https://github.com/LinkAnJarad/OpenChess-Insights) | MIT | 70 stars | README says "quite cluttered, and contains a lot of bugs"; skip |
| [sonirico/mcp-stockfish](https://github.com/sonirico/mcp-stockfish) | MIT | 16 stars, Go, 3 commits | Raw engine bridge with no mistake logic; we already wrap Stockfish with python-chess; skip |
| [jacokyle01/chess-srs](https://github.com/jacokyle01/chess-srs) | GPL-3.0 | 3 stars | Opening-only library; skip |
| [gtim/chessdriller](https://github.com/gtim/chessdriller) | None shown; **archived 3 Oct 2026** | 64 stars | Skip |

**Not read:** marcusbuffett/chess-tactics-cli (the fetch was refused); VelaChess (no repo found); Lichess MCP and ChessAgine MCP (403); any LICENSE file; any commit date.

## Licence check from the primary files (2026-11-08)

Read from the raw LICENSE, COPYING and package files, not the GitHub sidebar. This is a practical reading, not legal advice.

| Item | What the file says | Consequence |
|---|---|---|
| py-fsrs (PyPI `fsrs`) | MIT, "Copyright (c) 2022 Open Spaced Repetition"; version 6.3.2, released 9 Aug 2026; needs Python 3.10 or later (we use 3.12) | **Usable.** Add a `THIRD_PARTY.md` row first. Its required dependencies were not on the PyPI page; check them when installing |
| ts-fsrs | MIT, "Copyright (c) 2026 Open Spaced Repetition"; npm page returned 403 | Usable if scheduling ever runs in the browser. Not needed while scheduling stays on the backend |
| ornicar/lichess-puzzler | Unmodified AGPL-3.0 text, version 3. **No project copyright line and no licence header in the two source files read** (`generator.py`, `tagger/cook.py`). The "or later" wording appears only in the standard licence template | Treat as **AGPL-3.0 only**. Copying its code into this repo (AGPL-3.0-or-later) would tie that code to "only". **Do not copy; reimplement the idea** (how a single-answer position is chosen and tagged) |
| kraktus/lichess-puzzler | Same AGPL-3.0 text, same length | Same as above |
| brianch/lichess-puzzler | An MIT-style file, "Copyright 2020 lichess.org"; no licence name | Provenance unclear, since its parents are AGPL. **Do not rely on it** |
| lichess-org/chess-openings | `COPYING.txt` is CC0 1.0 Universal; no LICENSE file. `a.tsv` is 824 lines, 65.7 KB, columns eco, name, pgn | **Usable.** Needs the owner's OK to download and a `THIRD_PARTY.md` row |
| PvtTwinkle/Chessstack | `LICENSE` is AGPL-3.0; `package.json` says "AGPL-3.0-or-later"; depends on ts-fsrs ^5.2.3 | Compatible with this repo. Svelte/TypeScript, so a reference, not a drop-in |

Decision for the owner: reimplement the "single-answer position" check ourselves and use py-fsrs and the CC0 opening names. Nothing has been installed or downloaded.

## What this says

1. **A near-identical MCP idea exists and is easy to build.** Anyone can wrap Stockfish and let a model explain. The unreachable part is not the plumbing; it is verified claims, a measured baseline and tested detectors.
2. **Almost nothing reusable does the one thing we found unserved**: a puzzle or drill that starts from the position *before your first mistake*, chosen across all your games, with a single engine-verified better move.
3. **Reuse is mostly method and data, not code**: Lichess's puzzle generator for how to pick a single-answer position and tag its theme; Lichess's CC0 opening names; FSRS for review timing; Maia-3 for the opponent.
4. **Licence caution.** Two promising repos have no usable licence (litrainer, chessdriller) and one is MIT-labelled but forked from AGPL code. Ask before copying anything beyond a reference.
