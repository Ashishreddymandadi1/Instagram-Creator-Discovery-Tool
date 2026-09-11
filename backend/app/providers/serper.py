"""Serper.dev (Google SERP) provider. Free 2,500 one-time credits."""
from __future__ import annotations

import logging

import httpx

from app.providers.base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

_ENDPOINT = "https://google.serper.dev/search"


class SerperSearchProvider(SearchProvider):
    name = "serper"

    def __init__(self, api_key: str, timeout: float = 12.0) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not self.is_configured:
            return []
        # NOTE: Serper's free-tier plan rejects `site:` (and some other search
        # operator) queries outright with "Query pattern not allowed for free
        # accounts." So — unlike Tavily's include_domains — we never add
        # site:instagram.com here. Plain "<topic> instagram creator"-style
        # queries reliably surface real profile links anyway; the downstream
        # Instagram URL filter (providers/instagram_url.py) does the real
        # scoping by rejecting anything that isn't a genuine profile URL.
        plain = query.replace("site:", "").replace('"', "").strip()
        body = {"q": plain, "gl": "us", "hl": "en", "num": max(1, min(limit, 20))}
        headers = {"X-API-KEY": self._api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(_ENDPOINT, json=body, headers=headers)
            if resp.status_code != 200:
                logger.warning("Serper HTTP %s: %s", resp.status_code, resp.text[:200])
                return []
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Serper request failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for item in data.get("organic", []):
            url = item.get("link")
            if not url:
                continue
            results.append(
                SearchResult(
                    provider=self.name,
                    url=url,
                    title=item.get("title"),
                    snippet=item.get("snippet"),
                )
            )
        return results
