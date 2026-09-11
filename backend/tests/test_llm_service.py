"""LLM client: JSON extraction + retry/degradation behaviour."""
import pytest

from app.services.llm_service import (
    LLMService,
    LLMUnavailableError,
    _extract_json,
)


def test_extract_plain_json():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_from_fenced_block():
    assert _extract_json('```json\n{"a": 2}\n```') == {"a": 2}


def test_extract_json_embedded_in_prose():
    assert _extract_json('Sure! Here you go: {"a": 3} hope that helps') == {"a": 3}


def test_extract_returns_none_for_garbage():
    assert _extract_json("not json at all") is None
    assert _extract_json("") is None


def test_extract_returns_none_for_json_array_top_level():
    assert _extract_json("[1, 2, 3]") is None


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessages:
    """Fakes the underlying SDK's messages resource. Each `content` is the
    model's continuation AFTER the "{" assistant-turn prefill the service
    injects."""

    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return type("R", (), {"content": [_FakeBlock(self._contents.pop(0))]})()


class _FakeClient:
    def __init__(self, contents):
        self.messages = _FakeMessages(contents)


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    from app.config.settings import get_settings

    svc = LLMService(get_settings())
    fake = _FakeClient(["not valid json at all", '"ok": true}'])
    svc._client = fake
    result = await svc.complete_json([{"role": "user", "content": "x"}], max_retries=2)
    assert result == {"ok": True}
    assert fake.messages.calls == 2


@pytest.mark.asyncio
async def test_all_attempts_fail_raises():
    from app.config.settings import get_settings

    svc = LLMService(get_settings())
    fake = _FakeClient(["nope", "still nope", "nope again"])
    svc._client = fake
    with pytest.raises(LLMUnavailableError):
        await svc.complete_json([{"role": "user", "content": "x"}], max_retries=2)


@pytest.mark.asyncio
async def test_unconfigured_llm_raises():
    from app.config.settings import Settings

    svc = LLMService(Settings(anthropic_api_key=""))
    assert svc.is_configured is False
    with pytest.raises(LLMUnavailableError):
        await svc.complete_json([{"role": "user", "content": "x"}])
