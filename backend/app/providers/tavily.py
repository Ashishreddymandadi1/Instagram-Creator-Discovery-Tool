"""Tavily search provider — primary. Free dev tier, no credit card."""
from __future__ import annotations

import logging

import httpx

from app.providers.base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
    name = "tavily"

    def __init__(self, api_key: str, timeout: float = 12.0) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not self.is_configured:
            return []
        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, min(limit, 20)),
            "include_domains": ["instagram.com"],
            "include_answer": False,
            "include_raw_content": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(_ENDPOINT, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.warning("Tavily HTTP %s: %s", resp.status_code, resp.text[:200])
                return []
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Tavily request failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for item in data.get("results", []):
            url = item.get("url")
            if not url:
                continue
            results.append(
                SearchResult(
                    provider=self.name,
                    url=url,
                    title=item.get("title"),
                    snippet=item.get("content"),
                )
            )
        return results
