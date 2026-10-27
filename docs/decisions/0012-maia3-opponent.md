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
   Accepted range 400 to 2800 is a guard, not the model's documented range; narrow it after the under-1000 check.
4. **The full move list is sent** (`--use-uci-history`), because Maia-3 uses history. Default `Temperature` 1.0 (sample the model's
   human move distribution; 0 would repeat its top move). Both are env settings and are recorded in `maia.settings()`.
5. **Versioning (rule 6):** model alias, device and temperature come from `maia.settings()`. Seen on the first real run (2026-10-27): maia3 package commit `1e13597c`,
   `Maia3-5M` Hugging Face snapshot `b6559de2398d7140b985f28fd2c19fb5e47ddabe`, torch 2.14.1, CPU. Not yet recorded by the code per game.
6. **Practice and Play rules are unchanged** (ADR 0005). The opponent is not assistance. A Practice game against Maia is still assisted.
7. **Scope of this slice:** `POST /games` takes `opponent` ("stockfish" default, or "maia3") and `elo`. Not done: web selector,
   MCP `game_new` option, the under-1000 band check, checkpoint pinning.

## How to reverse
Do not set `MAIA3_CMD`: nothing changes, Stockfish stays the default and the only opponent. To remove it, delete `app/engine/maia.py`,
`opponent_elo` in `Game`, and the branches in `tools.py`.
