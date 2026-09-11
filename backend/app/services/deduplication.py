"""Candidate normalization and deduplication by lowercase Instagram handle.

Equivalent profile URL variants such as `instagram.com/TestCreator` and
`instagram.com/testcreator/` collapse to one candidate.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime

from app.providers.base import SearchResult
from app.providers.instagram_url import (
    extract_handle,
    extract_handle_from_text,
    handle_to_url,
    is_post_or_reel_url,
    normalize_instagram_url,
)

# How many evidence items per candidate are sent to the LLM and are therefore
# addressable by `evidence_indices`. Shared so analysis + persistence agree.
# Kept small to bound LLM token usage; enough for meaningful provenance.
MAX_EVIDENCE_PER_ANALYSIS = 3


def resolve_evidence_indices(indices: list[int], sent_count: int) -> list[int]:
    """Sanitize the LLM's `evidence_indices` against the evidence actually sent for
    a candidate: drop negatives and out-of-range, deduplicate, preserve order.
    Returns [] when nothing valid remains (caller applies a conservative
    fallback of "all evidence supplied to that analysis")."""
    seen: set[int] = set()
    out: list[int] = []
    for raw in indices or []:
        try:
            i = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= i < sent_count and i not in seen:
            seen.add(i)
            out.append(i)
    return out


@dataclass(slots=True)
class Candidate:
    handle: str                       # lowercase, no @
    instagram_url: str                # normalized canonical URL
    evidence: list[SearchResult] = field(default_factory=list)
    display_name: str | None = None

    @property
    def newest_retrieved_at(self) -> datetime | None:
        if not self.evidence:
            return None
        return max(e.retrieved_at for e in self.evidence)


def build_candidates(results: list[SearchResult]) -> list[Candidate]:
    """Filter to valid IG profile URLs, group evidence by handle, preserve order.

    Direct profile URLs are accepted as-is. An instagram.com post/reel URL is
    never returned as a candidate's profile URL, but if its title/snippet
    explicitly names the creator (an "@handle" token), the candidate is
    recovered under that handle's real profile URL — the post/reel link and
    its title/snippet are kept as evidence. Recovery never applies to a
    result whose own URL isn't confirmed instagram.com, and never invents a
    handle that isn't literally present in the text. A recovered handle
    dedupes with a directly-discovered profile for the same handle, same as
    any other evidence for that candidate.
    """
    grouped: "OrderedDict[str, Candidate]" = OrderedDict()
    for result in results:
        handle = extract_handle(result.url)
        if handle is not None:
            normalized = normalize_instagram_url(result.url)
        elif is_post_or_reel_url(result.url):
            handle = extract_handle_from_text(result.title, result.snippet)
            if handle is None:
                continue
            normalized = handle_to_url(handle)
        else:
            continue
        if normalized is None:
            continue
        if handle not in grouped:
            grouped[handle] = Candidate(handle=handle, instagram_url=normalized)
        grouped[handle].evidence.append(result)
    return list(grouped.values())


def merge_candidate_lists(*lists: list[Candidate]) -> list[Candidate]:
    merged: "OrderedDict[str, Candidate]" = OrderedDict()
    for candidates in lists:
        for cand in candidates:
            if cand.handle not in merged:
                merged[cand.handle] = Candidate(
                    handle=cand.handle, instagram_url=cand.instagram_url
                )
            existing = merged[cand.handle]
            seen_urls = {e.url for e in existing.evidence}
            for ev in cand.evidence:
                if ev.url not in seen_urls:
                    existing.evidence.append(ev)
                    seen_urls.add(ev.url)
            existing.display_name = existing.display_name or cand.display_name
    return list(merged.values())
