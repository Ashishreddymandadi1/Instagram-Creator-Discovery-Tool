"""LLM client wrapper: structured JSON completion with safe parsing + retries.

Uses the Anthropic SDK internally (a technical implementation detail — the
model/vendor is configurable via ANTHROPIC_MODEL). The model has no dedicated
"JSON mode" the way some providers do, so reliability comes from two things:
(1) the prompt instructs the model to return only JSON, and (2) we prefill the
assistant turn with "{" — a well-established technique that strongly biases
the model toward starting (and therefore staying in) a JSON object. Malformed
model output must never crash a request — callers get a raised error and
decide how to degrade.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from app.config.settings import Settings

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

# Prefilling the assistant turn with this strongly biases the model to emit a
# clean JSON object as the very next tokens.
_ASSISTANT_PREFILL = "{"


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM provider is not configured or all attempts failed."""


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):] if "{" in text else text
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = _JSON_OBJECT_RE.search(text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _split_system(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, str]]]:
    """The Anthropic API takes the system prompt as its own `system=`
    parameter, not as a message with role "system". Callers still build
    conventional role/content message lists (see prompts.py); this adapts
    them without touching every call site."""
    system_content = next((m["content"] for m in messages if m["role"] == "system"), None)
    rest = [dict(m) for m in messages if m["role"] != "system"]
    return system_content, rest


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.anthropic_model
        self._timeout = settings.anthropic_timeout_seconds
        self._client: anthropic.AsyncAnthropic | None = (
            anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key, timeout=settings.anthropic_timeout_seconds
            )
            if settings.llm_configured
            else None
        )

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        max_retries: int = 2,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Return a parsed JSON object. Raises LLMUnavailableError on total
        failure.

        Note: this SDK's Messages API has no `temperature` parameter (sampling
        is controlled via `output_config.effort` instead, which this case study
        intentionally leaves at the model default rather than tuning). Native
        JSON-schema structured output (`output_config.format`) is also
        available but not wired up here — the prompt-instructed JSON + prefill
        approach below is simpler to reason about and already reliable.
        """
        if self._client is None:
            raise LLMUnavailableError("ANTHROPIC_API_KEY is not configured")

        system_content, user_messages = _split_system(messages)
        prefilled = user_messages + [{"role": "assistant", "content": _ASSISTANT_PREFILL}]

        last_error: str = "unknown error"
        for attempt in range(1, max_retries + 2):
            try:
                resp = await self._client.messages.create(
                    model=self._model,
                    system=system_content or anthropic.NOT_GIVEN,
                    messages=prefilled,  # type: ignore[arg-type]
                    max_tokens=max_tokens,
                )
                text = "".join(
                    block.text for block in resp.content if getattr(block, "type", None) == "text"
                )
                content = _ASSISTANT_PREFILL + text
                parsed = _extract_json(content)
                if parsed is not None:
                    return parsed
                last_error = "model returned non-JSON content"
                logger.warning("LLM attempt %d: %s", attempt, last_error)
            except anthropic.AnthropicError as exc:
                last_error = f"LLM provider error: {exc}"
                logger.warning("LLM attempt %d failed: %s", attempt, exc)
            except (KeyError, IndexError, AttributeError) as exc:
                last_error = f"unexpected LLM response shape: {exc}"
                logger.warning("LLM attempt %d: %s", attempt, last_error)
        raise LLMUnavailableError(last_error)
