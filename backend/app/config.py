"""Settings from the environment. `.env` at the repo root is loaded if present."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

DATA_DIR = Path(os.environ.get("DATA_DIR", REPO_ROOT / "data"))  # git-ignored


def chesscom_username() -> str | None:
    return os.environ.get("CHESSCOM_USERNAME") or None


def chesscom_user_agent() -> str | None:
    return os.environ.get("CHESSCOM_USER_AGENT") or None


def case_study_time_controls() -> frozenset[str]:
    """Chess.com `time_control` strings counted in the case study (10|0 and 15|10)."""
    raw = os.environ.get("CASE_STUDY_TIME_CONTROLS", "600,900+10")
    return frozenset(t.strip() for t in raw.split(",") if t.strip())
