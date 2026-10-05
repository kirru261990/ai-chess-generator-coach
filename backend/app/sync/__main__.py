"""`uv run python -m app.sync` — sync the configured Chess.com account."""

import json
import sys

from app.sync.chesscom import SyncError, sync_chesscom

try:
    print(json.dumps(sync_chesscom(), indent=2))
except SyncError as e:
    sys.exit(f"{e.code}: {e}")
