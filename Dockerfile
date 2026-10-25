# The open chess connector (docs/public-connector.md, ADR 0010): games against Stockfish only. No database, no model key, no data.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends stockfish && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app

ENV STOCKFISH_PATH=/usr/games/stockfish \
    MCP_BIND=0.0.0.0 \
    PORT=7860
# MCP_PUBLIC_URL (the https address the host gives this service) is set in the host's settings, not here.
EXPOSE 7860
CMD ["uv", "run", "--no-sync", "python", "-m", "app.mcp.server", "public"]
