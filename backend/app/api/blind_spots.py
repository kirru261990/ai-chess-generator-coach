"""The blind-spot map's data (T16): the frozen baseline results, per time control (ADR 0002).

Read-only. The window is verified against its independent record and the results file's fingerprint is returned,
so the page can show exactly which frozen numbers it is displaying.
"""

import hashlib
import json

from app import config
from app.core.game import GameError
from app.learner import baseline
from app.learner.patterns import FROZEN_NAME


def baseline_blind_spots() -> dict:
    path = config.DATA_DIR / "baseline" / FROZEN_NAME
    if not path.exists():
        raise GameError("not_found", "the baseline results have not been frozen yet")
    data = path.read_bytes()
    results = json.loads(data)
    try:
        window = baseline.verify()
    except (baseline.BaselineError, OSError) as e:
        raise GameError("baseline_invalid", f"the baseline window does not match its record: {e}") from e
    if results.get("window_sha256") != window["sha256"]:
        raise GameError("baseline_invalid", "the frozen results belong to a different window")
    return {"results": results, "results_sha256": hashlib.sha256(data).hexdigest()}
