"""Best-effort keyless fallback using the DuckDuckGo HTML endpoint.

Low reliability by design — DuckDuckGo rate-limits and changes markup. This
exists so the tool degrades instead of dying when no keyed provider is
available, and is never the intended demo path.
"""
from __future__ import annotations

import html
import logging
import re

import httpx

from app.providers.base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

_ENDPOINT = "https://html.duckduckgo.com/html/"
_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    r'.*?(?:class="result__snippet"[^>]*>(?P<snippet>.*?)</a>)?',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip(text: str | None) -> str | None:
    if not text:
        return None
    return html.unescape(_TAG_RE.sub("", text)).strip() or None


class OptionalNoKeyProvider(SearchProvider):
    name = "keyless"

    def __init__(self, timeout: float = 12.0) -> None:
        self._timeout = timeout

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        params = {"q": query}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; GEOCreatorScout/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                resp = await client.get(_ENDPOINT, params=params, headers=headers)
            if resp.status_code != 200:
                logger.warning("keyless HTTP %s", resp.status_code)
                return []
            body = resp.text
        except httpx.HTTPError as exc:
            logger.warning("keyless request failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for match in _RESULT_RE.finditer(body):
            url = html.unescape(match.group("url") or "")
            if "instagram.com" not in url:
                continue
            results.append(
                SearchResult(
                    provider=self.name,
                    url=url,
                    title=_strip(match.group("title")),
                    snippet=_strip(match.group("snippet")),
                )
            )
            if len(results) >= limit:
                break
        return results
