import anthropic
import pytest

from app.coach import llm


def test_a_missing_credential_is_reported_as_unavailable_not_a_crash(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(name, raising=False)

    def no_credentials(*a, **k):  # the SDK raises a TypeError when it finds no credential at all
        raise TypeError("Could not resolve authentication method")

    monkeypatch.setattr(anthropic, "Anthropic", no_credentials)
    with pytest.raises(llm.CoachUnavailable):
        llm.AnthropicDrafter().draft("system", [{"role": "user", "content": "hi"}])


def test_the_model_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("COACH_MODEL", "some-model")
    assert llm.AnthropicDrafter().model == "some-model"
    monkeypatch.delenv("COACH_MODEL")
    assert llm.AnthropicDrafter().model == llm.DEFAULT_MODEL
