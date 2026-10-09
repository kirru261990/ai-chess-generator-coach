import json
from datetime import UTC, datetime

import anthropic
import pytest
from fastapi.testclient import TestClient

from app import config
from app.api.main import app
from app.coach import llm, usage

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.delenv("MONTHLY_BUDGET_USD", raising=False)
    return tmp_path


def test_prices_follow_the_list_and_unknown_models_are_assumed_expensive():
    assert usage.price_usd("claude-sonnet-5-5", 1_000_000, 1_000_000) == pytest.approx(12.0)
    assert usage.price_usd("claude-sonnet-5-5", 6752, 4910) == pytest.approx(0.0626, abs=1e-4)
    assert usage.price_usd("some-future-model", 1_000_000, 0) == usage.UNKNOWN_MODEL_PRICE[0]


def test_calls_are_recorded_and_summed_for_the_month_by_purpose():
    usage.record("claude-sonnet-5-5", 1000, 500, "coach_why")
    usage.record("claude-sonnet-5-5", 2000, 1000, "eval")
    s = usage.summary()
    assert s["calls"] == 2 and s["spent_usd"] == pytest.approx(0.0070 + 0.014, abs=1e-6)
    assert set(s["by_purpose"]) == {"coach_why", "eval"} and s["budget_usd"] == 10.0


def test_another_months_spend_does_not_count():
    old = datetime(2026, 9, 15, tzinfo=UTC)
    usage.record("claude-sonnet-5-5", 1_000_000, 1_000_000, "eval", now=old)
    assert usage.summary()["spent_usd"] == 0 and usage.summary("2026-09")["spent_usd"] == pytest.approx(12.0)


def test_the_guard_stops_calls_at_the_budget_and_not_before(monkeypatch):
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "1")
    usage.record("claude-sonnet-5-5", 40_000, 10_000, "coach_why")  # 0.18 dollars
    usage.check()  # still under
    usage.record("claude-sonnet-5-5", 500_000, 0, "eval")  # +1.00 dollar: over
    with pytest.raises(usage.BudgetExceeded):
        usage.check()


def test_a_zero_budget_blocks_everything(monkeypatch):
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "0")
    with pytest.raises(usage.BudgetExceeded):
        usage.check()


def test_a_bad_budget_setting_falls_back_to_the_default(monkeypatch):
    for bad in ("", "abc", "-5"):
        monkeypatch.setenv("MONTHLY_BUDGET_USD", bad)
        assert usage.budget_usd() == usage.DEFAULT_BUDGET_USD


def test_a_corrupt_ledger_line_is_skipped_not_fatal(isolated_ledger):
    usage.record("claude-sonnet-5-5", 1000, 1000, "coach_why")
    with usage.ledger_path().open("a") as f:
        f.write("{torn line\n[1,2,3]\n")
    assert usage.summary()["calls"] == 1


class FakeClient:
    """Stands in for anthropic.Anthropic: returns a canned response with token usage."""

    calls = 0

    def __init__(self, *a, **k):
        self.messages = self

    def create(self, **kw):
        FakeClient.calls += 1
        block = type("B", (), {"type": "text", "text": "hi"})()
        u = type("U", (), {"input_tokens": 1000, "output_tokens": 200})()
        return type("R", (), {"stop_reason": "end_turn", "content": [block], "usage": u})()


def test_the_drafter_records_each_call_with_its_purpose(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    d = llm.AnthropicDrafter(purpose="coach_intent")
    d.draft("system", [{"role": "user", "content": "x"}])
    row = usage.rows()[0]
    assert row["purpose"] == "coach_intent" and row["input"] == 1000 and row["output"] == 200


def test_the_drafter_makes_no_call_once_the_budget_is_spent(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "0.001")
    FakeClient.calls = 0
    d = llm.AnthropicDrafter()
    d.draft("s", [{"role": "user", "content": "x"}])  # the first call fits (the check is made before it)
    assert FakeClient.calls == 1
    with pytest.raises(llm.CoachUnavailable, match="budget"):
        d.draft("s", [{"role": "user", "content": "x"}])
    assert FakeClient.calls == 1  # nothing was sent


def test_an_exhausted_budget_makes_the_coach_fall_back_to_facts_not_fail(monkeypatch):
    # the harness already treats CoachUnavailable as 'show checked facts'; the guard raises exactly that
    assert issubclass(llm.CoachUnavailable, Exception)
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "0")
    with pytest.raises(llm.CoachUnavailable):
        llm.AnthropicDrafter().draft("s", [{"role": "user", "content": "x"}])


def test_the_usage_endpoint_reports_spend_and_budget(monkeypatch):
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "5")
    usage.record("claude-sonnet-5-5", 100_000, 50_000, "eval")
    r = client.get("/usage").json()
    assert r["budget_usd"] == 5.0 and r["spent_usd"] == pytest.approx(0.7) and r["remaining_usd"] == pytest.approx(4.3)
    assert json.dumps(r)  # plain JSON
