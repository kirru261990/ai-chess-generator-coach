"""Build the M3 eval set `missed_threat_v4`: the v3 builder and label rule, a new seed, other games, no `uncertain` class. Imports nothing from app/detectors/.

Run:  cd backend && uv run python ../evals/tools/lichess_stream_sample.py --games 9000 --out ../data/lichess/rapid_600_1200_2026-09_b.pgn
      cd backend && uv run python ../evals/tools/build_missed_threat_set_v4.py [--pgn PATH] [--data DIR]

Why a new set (ADR 0014): v2's first score on `missed_threat_v3` exposed a flaw (an even trade called a missed threat), so the fixed detector
(v3) must not be scored on that set. Rule: sets/missed_threat_v3/LABEL_RULE.md with Amendment 1 (the threat must still win after the move by
the exchange count), without `uncertain`. The `met` items are split 15 clean and 15 other_loss, to test defended-by-recapture moves.
Games already used by `missed_threat_v3` are skipped. Writes candidates.jsonl, provenance.json and the owner's check key and page
(make_check_page_v4.py). It does not freeze.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_missed_threat_set_v3 as B3

if __name__ == "__main__":
    B3.configure("missed_threat_v4", 20261101, {"missed": 30, "met": 30, "not_applicable": 30}, {"clean": 15, "other_loss": 15},
                 {"missed": 8, "met": 8, "not_applicable": 8}, "missed_threat_v3")
    B3.main()
