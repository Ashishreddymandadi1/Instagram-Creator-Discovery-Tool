"""Evidence enrichment for candidates.

- Extract a best-effort display name from search-result titles (may stay None).
- For thin candidates, optionally run ONE extra targeted query, with a hard cap
  on total enrichment requests to control search-provider credit usage.
No Instagram scraping. Everything is web-search evidence.
"""
from __future__ import annotations

import asyncio
import logging
import re

from app.providers.base import SearchProvider
from app.services.deduplication import Candidate

logger = logging.getLogger(__name__)

# "Jane Smith (@janesmith) ..." or "Jane Smith | Something (@janesmith) ..."
_NAME_PAREN_RE = re.compile(r"^\s*(.{2,70}?)\s*\(@?[\w.]+\)\s*(?:[|•\-—]|on Instagram|$)")
# "Jane Smith on Instagram: ..."
_NAME_ON_IG_RE = re.compile(r"^\s*([^|•(]{2,60}?)\s+on Instagram", re.IGNORECASE)
# "Jane Smith (@janesmith) • Instagram photos and videos" -> take text before " • Instagram"
_NAME_BULLET_RE = re.compile(r"^\s*([^|•(]{2,60}?)\s*[•|]\s*Instagram", re.IGNORECASE)
_BAD_NAME_TOKENS = ("instagram", "photos and videos", "login", "explore", "http")


def _clean_name(raw: str) -> str | None:
    name = raw.strip(" .:|-—•")
    # if it still has a " | tagline", keep the part before the first pipe
    name = name.split("|")[0].strip(" .:-—•")
    low = name.lower()
    if 2 <= len(name) <= 60 and not any(tok in low for tok in _BAD_NAME_TOKENS):
        return name
    return None

_MIN_EVIDENCE_FOR_SKIP = 2
# Bounded to control search-provider credit usage; only thin candidates
# (< _MIN_EVIDENCE_FOR_SKIP evidence items) ever consume one of these.
_MAX_ENRICHMENT_QUERIES = 4


def _guess_display_name(candidate: Candidate) -> str | None:
    for ev in candidate.evidence:
        title = (ev.title or "").strip()
        if not title:
            continue
        for pattern in (_NAME_PAREN_RE, _NAME_BULLET_RE, _NAME_ON_IG_RE):
            m = pattern.match(title)
            if m:
                name = _clean_name(m.group(1))
                if name:
                    return name
    return None


async def enrich_candidates(
    candidates: list[Candidate],
    providers: list[SearchProvider],
    *,
    brief_topics: list[str],
) -> list[str]:
    """Mutates candidates in place (display_name, extra evidence). Returns warnings."""
    warnings: list[str] = []

    for cand in candidates:
        cand.display_name = cand.display_name or _guess_display_name(cand)

    keyed = [p for p in providers if p.name != "keyless"]
    if not keyed:
        return warnings

    thin = [c for c in candidates if len(c.evidence) < _MIN_EVIDENCE_FOR_SKIP]
    thin = thin[:_MAX_ENRICHMENT_QUERIES]
    if not thin:
        return warnings

    topic_hint = " ".join(brief_topics[:3]) if brief_topics else "AI search marketing"
    provider = keyed[0]

    async def _one(cand: Candidate) -> None:
        name = cand.display_name or cand.handle
        query = f"{name} {cand.handle} instagram {topic_hint}"
        try:
            extra = await provider.search(query, limit=5)
        except Exception as exc:  # never let enrichment kill the search
            logger.warning("Enrichment query failed for %s: %s", cand.handle, exc)
            return
        seen = {e.url for e in cand.evidence}
        for r in extra:
            from app.providers.instagram_url import extract_handle

            if extract_handle(r.url) == cand.handle and r.url not in seen:
                cand.evidence.append(r)
                seen.add(r.url)

    await asyncio.gather(*(_one(c) for c in thin))
    return warnings
