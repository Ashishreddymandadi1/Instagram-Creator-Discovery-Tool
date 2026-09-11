"""Brave Search provider. NOTE: Brave removed its free tier in Feb 2026 — a
credit card is now required. Kept for provider-abstraction completeness."""
from __future__ import annotations

import logging

import httpx

from app.providers.base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str, timeout: float = 12.0) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not self.is_configured:
            return []
        scoped = query if "site:" in query.lower() else f"site:instagram.com {query}"
        params = {"q": scoped, "count": max(1, min(limit, 20))}
        headers = {"Accept": "application/json", "X-Subscription-Token": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(_ENDPOINT, params=params, headers=headers)
            if resp.status_code != 200:
                logger.warning("Brave HTTP %s: %s", resp.status_code, resp.text[:200])
                return []
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Brave request failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for item in (data.get("web", {}) or {}).get("results", []):
            url = item.get("url")
            if not url:
                continue
            results.append(
                SearchResult(
                    provider=self.name,
                    url=url,
                    title=item.get("title"),
                    snippet=item.get("description"),
                )
            )
        return results
