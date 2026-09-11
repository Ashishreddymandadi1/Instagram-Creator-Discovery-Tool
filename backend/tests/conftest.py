"""Shared test fixtures. No network: the LLM + search providers are faked."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.db_models import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


class FakeProvider:
    """Deterministic in-memory SearchProvider."""

    def __init__(self, name: str, results_by_query: dict | None = None, raises: bool = False):
        self.name = name
        self._results = results_by_query or {}
        self._raises = raises
        self.is_configured = True
        self.calls: list[str] = []

    async def search(self, query: str, limit: int = 10):
        self.calls.append(query)
        if self._raises:
            raise RuntimeError(f"{self.name} boom")
        from app.providers.base import SearchResult
        from datetime import datetime, timezone

        out = []
        for url, title, snippet in self._results.get("*", []) + self._results.get(query, []):
            out.append(
                SearchResult(
                    provider=self.name, url=url, title=title, snippet=snippet,
                    retrieved_at=datetime.now(timezone.utc),
                )
            )
        return out[:limit]


class FakeLLM:
    """Returns canned JSON dicts in sequence, or raises LLMUnavailableError."""

    def __init__(self, responses: list | None = None, unavailable: bool = False):
        self._responses = list(responses or [])
        self._unavailable = unavailable
        self.is_configured = not unavailable

    async def complete_json(self, messages, **kwargs):
        from app.services.llm_service import LLMUnavailableError

        if self._unavailable:
            raise LLMUnavailableError("test: llm off")
        if not self._responses:
            raise LLMUnavailableError("test: no more canned responses")
        return self._responses.pop(0)


@pytest.fixture
def fake_llm_factory():
    return FakeLLM


@pytest.fixture
def fake_provider_factory():
    return FakeProvider
