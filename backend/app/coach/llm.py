"""The coach LLM behind a small interface, so the harness and its tests never need a key or a network (rule 1).

`AnthropicDrafter` calls the Anthropic API with the model in `COACH_MODEL`. It returns text only; nothing it says is
shown until the verifier has checked it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 4000


class CoachUnavailable(Exception):
    """No usable coach model (no key, a refusal, or an API failure)."""


@dataclass(frozen=True)
class Draft:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class Drafter(Protocol):
    model: str

    def draft(self, system: str, messages: list[dict]) -> Draft: ...


class AnthropicDrafter:
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("COACH_MODEL") or DEFAULT_MODEL

    def draft(self, system: str, messages: list[dict]) -> Draft:
        import anthropic  # imported here so the rest of the app works without a key

        try:
            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY (or another configured credential)
            response = client.messages.create(
                model=self.model, max_tokens=MAX_TOKENS, system=system, messages=messages
            )
        except (anthropic.AnthropicError, TypeError) as e:  # no credential (TypeError), rate limit, network, bad request
            raise CoachUnavailable(f"{type(e).__name__}: {e}") from e
        if response.stop_reason == "refusal":
            raise CoachUnavailable("the model declined this request")
        text = "".join(b.text for b in response.content if b.type == "text")
        return Draft(text, self.model, response.usage.input_tokens, response.usage.output_tokens)
