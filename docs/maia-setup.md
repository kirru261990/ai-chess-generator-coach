# Maia-3 opponent setup (ADR 0012)

Maia-3 is optional. Without it the app plays Stockfish only.

1. Install it in its own environment (it brings PyTorch, several hundred MB; weights download on first run):
   ```bash
   uv tool install git+https://github.com/CSSLab/maia3
   maia3-cache --model maia3-5m
   ```
2. In the git-ignored `.env`: `MAIA3_CMD=maia3-uci` (a full path or a command line also works), optionally `MAIA3_MODEL=maia3-5m`,
   `MAIA3_DEVICE=cpu`, `MAIA3_TEMPERATURE=1.0`.
3. Restart the API (no auto-reload), then start a game:
   ```bash
   curl -s localhost:8000/games -H 'content-type: application/json' -d '{"mode":"practice","opponent":"maia3","elo":900}'
   ```
   `opponent_unavailable` means step 1 or 2 is missing. The Elo is what the model is conditioned on, not a measured strength.
