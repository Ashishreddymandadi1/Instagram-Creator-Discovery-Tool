"""Creator discovery: run search queries across providers concurrently, collect
20-40 raw candidate results, turn them into deduped Candidates."""
from __future__ import annotations

import asyncio
import logging

from app.providers.base import SearchProvider, SearchResult
from app.services.deduplication import Candidate, build_candidates

logger = logging.getLogger(__name__)

# Cap concurrent outbound search requests to stay under free-tier rate limits.
_MAX_CONCURRENCY = 5


class DiscoveryOutcome:
    __slots__ = ("candidates", "raw_result_count", "provider_errors", "providers_used")

    def __init__(
        self,
        candidates: list[Candidate],
        raw_result_count: int,
        provider_errors: list[str],
        providers_used: list[str],
    ):
        self.candidates = candidates
        self.raw_result_count = raw_result_count
        self.provider_errors = provider_errors
        self.providers_used = providers_used


async def _run_one(
    provider: SearchProvider,
    query: str,
    per_query_limit: int,
    sem: asyncio.Semaphore,
) -> tuple[str, list[SearchResult] | Exception]:
    try:
        async with sem:
            return provider.name, await provider.search(query, per_query_limit)
    except Exception as exc:  # defensive: providers shouldn't raise, but never let one kill discovery
        logger.warning("Provider %s raised on %r: %s", provider.name, query, exc)
        return provider.name, exc


async def discover_candidates(
    providers: list[SearchProvider],
    search_queries: list[str],
    *,
    max_candidates: int,
    per_query_limit: int = 10,
) -> DiscoveryOutcome:
    if not providers:
        return DiscoveryOutcome([], 0, ["No search providers are configured."], [])

    sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    tasks = [
        _run_one(provider, query, per_query_limit, sem)
        for query in search_queries
        for provider in providers
    ]
    settled = await asyncio.gather(*tasks)

    all_results: list[SearchResult] = []
    provider_errors: list[str] = []
    providers_ok: set[str] = set()
    providers_failed: set[str] = set()

    for name, outcome in settled:
        if isinstance(outcome, Exception):
            providers_failed.add(name)
            continue
        if outcome:
            providers_ok.add(name)
        all_results.extend(outcome)

    for name in providers_failed:
        if name not in providers_ok:
            provider_errors.append(f"Search provider '{name}' failed for this search.")

    candidates = build_candidates(all_results)
    if len(candidates) > max_candidates:
        candidates = candidates[:max_candidates]

    return DiscoveryOutcome(
        candidates=candidates,
        raw_result_count=len(all_results),
        provider_errors=provider_errors,
        providers_used=sorted(providers_ok),
    )
