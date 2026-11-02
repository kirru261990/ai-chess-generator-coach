# 0016 — Maia-3 in the open connector

Status: accepted, 2026-11-02, **built but not yet deployed or run on Render**. Decided by: Claude on the owner's request ("update the
connector to include the Maia changes"); reversible (see the end). Builds on ADR 0010 (open connector) and ADR 0012 (Maia-3).

## What changed
- The code needed no new feature: the open server already accepts `game_new opponent=maia3 elo=...` (the tool is shared with the
  private server). What was missing was Maia-3 inside the Render image, so the call answered "Maia-3 is not installed".
- `Dockerfile`: a separate venv `/opt/maia3` with CPU-only PyTorch and `maia3` pinned to commit `1e13597c42d4...` (the commit of the
  first real run, ADR 0012 decision 5; build arg `MAIA3_REF`). The `maia3-5m` weights are fetched **at build time** into `/opt/hf`
  and the runtime is offline (`HF_HUB_OFFLINE=1`), so a sleeping instance never downloads on a player's first move.
  `MAIA3_CMD=/opt/maia3/bin/maia3-uci` is set in the image.
- `PUBLIC_INSTRUCTIONS` and the privacy page name Maia-3. The page now says no *outside* AI service is called and that Maia-3 runs
  inside the server (it is a local model; the "no model call" line in ADR 0010 meant a paid API, which is still true).
- Tests: the open server plays a Maia game with a stand-in engine and refuses cleanly when Maia-3 is missing.

## Risks, stated plainly
1. **Memory.** Render's free instance has 512 MB and 0.1 CPU. PyTorch plus the 5M model may use 250 to 400 MB on top of the web server
   and Stockfish. Maia starts lazily (first Maia game), so the service runs as before until then; if the first Maia game gets the
   process killed (out of memory), the whole service restarts. Not measured. If it happens: set `MAIA3_CMD` blank in Render (off), or
   move to a paid instance.
2. **Build.** The image build installs about 200 MB of PyTorch (CPU wheel) and may be slow on Render's free builder. The Dockerfile was
   not built here (Docker is not installed on this Mac).
3. **Weights licence is still unknown** (ADR 0012). The weights are downloaded from the upstream Hugging Face page at build time and
   stay inside the image; they are not committed or offered for download. Find the licence before listing the connector in a directory.
4. **Speed.** One forward pass per move on 0.1 CPU; expected to be a second or a few. Not measured.

## Measured on Render, 2026-11-02 (first deploy)
Stockfish moves 0.5 to 1.4 s; Maia-3 moves 9.7 to 10.7 s each, so risk 4 happened and the model load is not the cause. Memory was not
read from the Metrics graph. Tried first: `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1` (a guess that thread contention on 0.1 CPU is the
cause; result to be recorded here after the redeploy).

## How to reverse
Set `MAIA3_CMD` to a blank value in Render's environment (off, no rebuild), or revert the Dockerfile block. Games then answer
`opponent_unavailable` for Maia and the chat offers Stockfish.
