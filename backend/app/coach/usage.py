"""Model spend ledger and monthly budget guard.

Every call to the Anthropic API is recorded (tokens and estimated dollars) in `data/usage/usage_YYYY-MM.jsonl` (git-ignored). Before
each call the guard refuses to proceed when this month's recorded spend has reached `MONTHLY_BUDGET_USD`; the coach then falls
back to checked facts, as it does without a key.

Limits, stated plainly: dollars are estimated from the list prices below, which can drift; the Anthropic Console is the
authority and a spending limit set there is the real hard stop. The ledger only knows about calls made through this code,
starting from the day it was added; earlier spend (the first eval runs) is not in it. A call that fails after being sent is not
recorded. The check is made before a call, so one call can overshoot the budget by its own cost.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from app import config

DEFAULT_BUDGET_USD = 10.0
# USD per million tokens (input, output): list prices as of 2026-09-25.
PRICES = {
    "claude-fable-5-1": (10.0, 50.0), "claude-fable-5": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0), "claude-opus-5": (5.0, 25.0), "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0), "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0), "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
UNKNOWN_MODEL_PRICE = (10.0, 50.0)  # an unknown model is assumed to be the most expensive one, never the cheapest


class BudgetExceeded(Exception):
    """This month's recorded model spend has reached the budget."""


def price_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(model, UNKNOWN_MODEL_PRICE)
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


def budget_usd() -> float:
    raw = os.environ.get("MONTHLY_BUDGET_USD")
    try:
        value = float(raw) if raw else DEFAULT_BUDGET_USD
    except ValueError:
        return DEFAULT_BUDGET_USD
    return value if value >= 0 else DEFAULT_BUDGET_USD


def month_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def ledger_path(month: str | None = None) -> Path:
    return config.DATA_DIR / "usage" / f"usage_{month or month_key()}.jsonl"


def record(model: str, input_tokens: int, output_tokens: int, purpose: str, now: datetime | None = None) -> float:
    """Append one call to this month's ledger. Returns its estimated cost in dollars."""
    now = now or datetime.now(UTC)
    usd = price_usd(model, input_tokens, output_tokens)
    path = ledger_path(month_key(now))
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": now.isoformat(timespec="seconds"), "model": model, "input": input_tokens, "output": output_tokens,
           "usd": round(usd, 6), "purpose": purpose}
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return usd


def rows(month: str | None = None) -> list[dict]:
    path = ledger_path(month)
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue  # a torn or corrupt line is skipped, never fatal
        if isinstance(row, dict) and isinstance(row.get("usd"), (int, float)):
            out.append(row)
    return out


def summary(month: str | None = None) -> dict:
    data = rows(month)
    spent = sum(r["usd"] for r in data)
    by_purpose: dict[str, float] = {}
    for r in data:
        by_purpose[r.get("purpose", "?")] = round(by_purpose.get(r.get("purpose", "?"), 0) + r["usd"], 4)
    budget = budget_usd()
    return {"month": month or month_key(), "spent_usd": round(spent, 4), "budget_usd": budget,
            "remaining_usd": round(max(0.0, budget - spent), 4), "calls": len(data), "by_purpose": by_purpose}


def check() -> None:
    """Raise BudgetExceeded if this month's recorded spend has reached the budget."""
    s = summary()
    if s["spent_usd"] >= s["budget_usd"]:
        raise BudgetExceeded(
            f"this month's model spend (${s['spent_usd']:.2f}) has reached the budget (${s['budget_usd']:.2f}); "
            "raise MONTHLY_BUDGET_USD in .env to continue"
        )
