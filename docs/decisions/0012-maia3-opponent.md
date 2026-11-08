# 0012 — Maia-3 as the human-like practice opponent (replaces the Maia-2 plan)

Status: accepted, 2026-10-27 (first slice: backend only). Decided by: Claude on the owner's request ("integrate Maia-3");
reversible (see the end). Supersedes the Maia-2 line in ADR 0001 and spec A2; implements the start of TASKS T28.

## Why Maia-3, not Maia-2
The Maia-2 README now points new projects to Maia-3 (CSSLab/maia3). The owner asked for Maia-3.

## Facts checked on 2026-10-27 (from the repository and model card pages, not run yet)
- Code: **AGPL-3.0**, compatible with this repo (AGPL-3.0-or-later). Not a Python dependency of ours (see decision 1).
- **Weights licence: not stated** on the repo page or the Hugging Face card for `UofTCSSLab/Maia3-5M` ("see repo"). We do not
  redistribute weights (they download on first run), so this does not block use, but find the licence before shipping them anywhere.
- **Supported rating range: not stated.** Spec A2 asks whether the lowest band works for players under 1000. Unchecked.
- Sizes: 3M (ablation), 5M (recommended for CPU), 23M, 79M. The card says "not intended for maximum playing strength".
- Interface: UCI (`maia3-uci`), options `Elo`, `SelfElo`, `OppoElo`, `Temperature` (0 = top move), `TopP`; `go nodes 1`.

## Decisions
1. **A separate UCI process, like Stockfish.** `app/engine/maia.py` starts `MAIA3_CMD` and talks UCI through python-chess.
   PyTorch stays out of `pyproject.toml`; Maia-3 is installed in its own environment (`docs/maia-setup.md`).
2. **Never swap the opponent silently.** A Maia-3 game when Maia-3 is not installed fails with `opponent_unavailable`; the client
   offers Stockfish. The PGN and the game view name the opponent, so a game is never mislabelled.
3. **Strength is a label, not an Elo claim.** The `elo` is what the model is conditioned on. Shown as "Maia-3 (maia3-5m) at 900".
   The accepted range is 500 to 2000 since the band check of 2026-11-08 (below); it was 400 to 2800 as a guard.
4. **The full move list is sent** (`--use-uci-history`), because Maia-3 uses history. Default `Temperature` 1.0 (sample the model's
   human move distribution; 0 would repeat its top move). Both are env settings and are recorded in `maia.settings()`.
5. **Versioning (rule 6):** model alias, device and temperature come from `maia.settings()`. Seen on the first real run (2026-10-27): maia3 package commit `1e13597c`,
   `Maia3-5M` Hugging Face snapshot `b6559de2398d7140b985f28fd2c19fb5e47ddabe`, torch 2.14.1, CPU. Recorded per game since 2026-11-08 (see below).
6. **Practice and Play rules are unchanged** (ADR 0005). The opponent is not assistance. A Practice game against Maia is still assisted.
7. **Web and chat (second slice):** `GET /opponents` says whether Maia-3 is installed; the web app shows an Opponent choice and a Rating list (600 to 2000) only then. MCP `game_new` takes `opponent` and `elo`.
8. **Scope of the first slice:** `POST /games` takes `opponent` ("stockfish" default, or "maia3") and `elo`. Not done: web selector,
   MCP `game_new` option, the under-1000 band check, checkpoint pinning (both done 2026-11-08, see below).

## How to reverse
Do not set `MAIA3_CMD`: nothing changes, Stockfish stays the default and the only opponent. To remove it, delete `app/engine/maia.py`,
`opponent_elo` and `opponent_setup` in `Game`, and the branches in `tools.py`.


## Band check and checkpoint (2026-11-08)

**Question (spec A2):** does the Elo setting change how Maia-3 plays, down to players under 1000?
**Method:** `evals/tools/maia_band_check.py`, report `evals/reports/maia_band_check_2026-11-08.json` (it records the date, the tool's commit and the setup that ran). 300 positions
(plies 12 to 50) from real Lichess rapid games where both players are rated 900 or lower (the September 2026 sample, seed 7). The rating of the player to move:
500s: 13, 600s: 56, 700s: 116, 800s: 114, 900s: 1, so players near 500 are scarce. For each setting from 500 to 2000, Maia-3 (maia3-5m, CPU, temperature 1.0) played one sampled move per position, scored by Stockfish at depth 10.
The move the real player made in the same position is scored the same way, which gives a human baseline. Each board is rebuilt by replaying every earlier move, so Maia-3
gets the same history as in a live game. Scores keep a mate above any centipawn lead (centipawns clamped to 900, a mate is 1000, and a mate just delivered counts as a win).
Intervals are 95% bootstrap intervals over positions. The top-move match is a separate run at temperature 0, so it is not the same experiment as the loss. A first version used the position
alone and python-chess's mate scoring, and a second still scored a delivered mate as a loss; all were corrected after review (PR 120), and this table is the corrected run.

| Setting | Moves losing 200 cp or more (95% interval) | Mean loss, cp (95% interval) | Top move equals the real move (95% interval) |
|---|---|---|---|
| 500 | 31.3% (26.0 to 36.7) | 198 (164 to 234) | 50.0% (44.7 to 55.7) |
| 700 | 20.0% (15.7 to 24.7) | 132 (106 to 162) | 51.7% (46.0 to 57.0) |
| 900 | 20.7% (16.0 to 25.3) | 141 (112 to 175) | 51.0% (45.3 to 56.7) |
| 1200 | 13.7% (10.0 to 17.7) | 90 (72 to 108) | 48.0% (42.7 to 53.7) |
| 1600 | 12.7% (9.0 to 16.7) | 80 (66 to 96) | 48.7% (43.0 to 54.3) |
| 2000 | 10.3% (7.0 to 13.7) | 77 (59 to 98) | 47.3% (41.7 to 53.0) |
| **real players (rated 900 or lower)** | **16.7%** (12.3 to 21.0) | **125** (98 to 155) | n/a |

Conditioned on each real player's own rating (nearest 100), the top move equals the real move in 51.3%.

**What it shows:**
- A lower setting plays measurably weaker down to 500, in three steps. The share of big mistakes, paired over the same positions:
  - 700 against 500: -11.3 points (-17.3 to -5.0)
  - 900 against 700: +0.7 points (-4.3 to +6.0)
  - 1200 against 900: -7.0 points (-11.7 to -2.3)
  - 1600 against 1200: -1.0 points (-5.3 to +3.3)
  - 2000 against 1600: -2.3 points (-6.7 to +2.0)
  The 500 to 700 and 900 to 1200 steps are clear; 700 and 900 are not different, and neither are 1200, 1600 and 2000.
- **The 500 setting is not a 500-rated player.** In these positions real players rated 900 or lower lose 200 cp or more 16.7% of the time; the 500 setting
  does it 31.3% of the time, nearly twice as often. The settings 700 to 1200 sit closest to those real players. Maia-3's lowest settings are weaker
  than real beginners at making moves, not like them.
**What it does not show:**
- That Maia-3 plays like a player of that rating. The top-move match is 47.3% to 51.7% at every setting, with
  intervals of about 11 points that all overlap. The setting is a strength dial, not a rating.
- Anything about 1200 to 2000. In these positions those settings look alike, which may be the test, not the model: the positions come from players rated 900 or lower, so only gross errors show at depth 10.
- Anything below 500 or above 2000. They were not tried. One sampled move per position and one seed: the intervals do not cover that sampling.

**Decisions:**
1. The accepted range is **500 to 2000** (`maia.MIN_ELO`, `MAX_ELO`). The label stays "Maia-3 (maia3-5m) at 900", never an Elo claim. Do not describe the low settings as beginner play.
2. **The setup is recorded on every Maia game.** `maia.setup_for()` gives model, device, temperature, the Hugging Face snapshot hash, where that hash came from (`hf_cache` or `override`) and whether it equals
   the snapshot the check ran on. It is read from this computer's cache right after the Maia-3 process starts; it is the cache's current snapshot, not a report from the process, and with
   `MAIA3_CHECKPOINT` set it is an assertion by whoever set it. A game takes the record once Maia-3 has played a move that was accepted. A later move by a different process (a restart) keeps the
   first record and marks it `setup_changed`; a move that is rejected records nothing. Before Maia-3 has moved, `opponent_setup` is empty. It is in the game view, the chat game data and a PGN `OpponentSetup`
   header. A game on another snapshot is recorded as not pinned, never refused. The earlier note of the maia3 package commit and torch version is not recorded per game.
3. The owner played a first real game against it on 2026-11-08 (Play mode, the owner as White, Maia-3 at 1600, 84 plies, the owner resigned, no help used, checkpoint pinned; PGN in the git-ignored `data/maia/`). The owner said the 1600 setting felt right against their play (a subjective report from one game; their Chess.com rapid rating is about 690, so the setting is a dial, not a rating on that scale). One game says only that it plays end to end. Still open: the weights licence (not stated).
