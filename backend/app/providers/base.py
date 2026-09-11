"""Search provider abstraction. Scoring is never coupled to a concrete provider."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class SearchResult:
    provider: str
    url: str
    title: str | None = None
    snippet: str | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    synthetic: bool = False


class SearchProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Run one query. Must never raise for an expected failure (no key, HTTP
        error, timeout) — return [] and let the orchestrator record a warning."""
        raise NotImplementedError

    @property
    def is_configured(self) -> bool:
        return True
