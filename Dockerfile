# The open chess connector (docs/public-connector.md, ADRs 0010 and 0016): games against Stockfish or Maia-3. No database, no model key, no data.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends stockfish && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app

# Maia-3 (ADR 0012, 0016): its own venv with CPU-only PyTorch, pinned to the commit seen on the first real run (2026-10-27).
# Weights are fetched at build time into /opt/hf so a sleeping instance never downloads them on a player's first move.
ARG MAIA3_REF=1e13597c42d4858b7cfd7cfdae01e297263364b2
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/maia3 \
    && /opt/maia3/bin/pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && /opt/maia3/bin/pip install --no-cache-dir "git+https://github.com/CSSLab/maia3@${MAIA3_REF}" \
    && HF_HOME=/opt/hf /opt/maia3/bin/maia3-cache --model maia3-5m \
    && apt-get purge -y git && apt-get autoremove -y

ENV STOCKFISH_PATH=/usr/games/stockfish \
    MAIA3_CMD=/opt/maia3/bin/maia3-uci \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    MCP_BIND=0.0.0.0 \
    PORT=7860
# To switch Maia-3 off without a rebuild, set MAIA3_CMD to a blank value in the host's settings (games then offer Stockfish only).
# MCP_PUBLIC_URL (the https address the host gives this service) is set in the host's settings, not here.
EXPOSE 7860
CMD ["uv", "run", "--no-sync", "python", "-m", "app.mcp.server", "public"]
