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
`opponent_elo` in `Game`, and the branches in `tools.py`.


## Band check and checkpoint (2026-11-08)

**Question (spec A2):** does the Elo setting change how Maia-3 plays, down to players under 1000?
**Method:** `evals/tools/maia_band_check.py`, report `evals/reports/maia_band_check_2026-11-08.json`. 300 positions (plies 12 to 50) from real
Lichess rapid games where both players are rated 900 or lower (the September 2026 sample, seed 7). For each setting from 500 to 2000,
Maia-3 (maia3-5m, CPU, temperature 1.0) played one sampled move per position, scored by Stockfish at depth 10. Each board is rebuilt by replaying every earlier
move, so Maia-3 gets the same history as in a live game; scores are kept so that a mate always outranks any centipawn lead (centipawns clamped to 900, a mate is 1000).
A first version of the check used the position alone and python-chess's mate scoring; both were corrected after review (PR 120) and the table below is the corrected run.

| Setting | Moves losing 200 cp or more | Mean loss (cp) | Top move equals the real move |
|---|---|---|---|
| 500 | 32.7% | 217 | 50.0% |
| 700 | 21.7% | 162 | 51.7% |
| 900 | 20.7% | 161 | 51.0% |
| 1200 | 12.7% | 102 | 48.0% |
| 1600 | 12.7% | 105 | 48.7% |
| 2000 | 10.7% | 97 | 47.3% |

Conditioned on each real player's own rating (nearest 100), the top move equals the real move in 51.3%.

**What it shows:** a lower setting plays measurably weaker, down to 500. Mistakes fall in three steps (500; 700 to 900; 1200 to 2000), with the same positions
for every setting. Roughly, a difference of about 4 points in the share is within noise at 300 positions; the steps are larger than that.
**What it does not show:**
- That Maia-3 plays like a player of that rating. How often its top move equals a real player's move is about the same (47 to 52%) at every setting, including the
  player's own rating (51.3%). The 3 to 4 point gap between the low and high settings is within the noise of 300 positions. The setting is a strength dial, not a rating.
- Anything about 1200 to 2000. In these positions those settings look alike (11 to 13%), which may be the test, not the model: the positions come from games
  between players rated 900 or lower, so only gross errors show at depth 10.
- Anything below 500 or above 2000. They were not tried.

**Decisions:**
1. The accepted range is **500 to 2000** (`maia.MIN_ELO`, `MAX_ELO`). The label stays "Maia-3 (maia3-5m) at 900", never an Elo claim.
2. **The checkpoint is recorded on every Maia game.** `maia.setup_for()` gives model, device, temperature, the Hugging Face snapshot
   hash read from the local cache (`MAIA3_CHECKPOINT` overrides it) and whether it equals the snapshot the check ran on. It is read once, when the Maia-3 process
   starts, and a game takes that record at the first move that process plays for it (a game never claims a setup the running process does not have; before
   Maia has moved, `opponent_setup` is empty). The game view carries it as
   `opponent_setup`. A game on another snapshot is recorded as not pinned, never refused.
3. The owner played a first real game against it on 2026-11-08 (Play mode, the owner as White, Maia-3 at 1600, 84 plies, the owner resigned, no help used, checkpoint pinned; PGN in the git-ignored `data/maia/`). The owner said the 1600 setting felt right against their play (a subjective report from one game; their Chess.com rapid rating is about 690, so the setting is a dial, not a rating on that scale). One game says only that it plays end to end. Still open: the weights licence (not stated).
