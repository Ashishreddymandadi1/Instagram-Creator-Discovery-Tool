"""Brief -> structured SearchCriteria via the LLM, with a deterministic fallback."""
from __future__ import annotations

import logging
import re

from app.models.schemas import SearchCriteria
from app.services.llm_service import LLMService, LLMUnavailableError
from app.services.prompts import build_brief_parse_messages

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    "find creators creator instagram who cover covering could be relevant our to "
    "and or the a an of for on about talking discuss discussing that are with "
    "content make making create creating people person show me".split()
)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+/&-]{2,}")

_MAX_QUERIES = 8


class QueryParseResult:
    __slots__ = ("criteria", "used_fallback", "warnings")

    def __init__(self, criteria: SearchCriteria, used_fallback: bool, warnings: list[str]):
        self.criteria = criteria
        self.used_fallback = used_fallback
        self.warnings = warnings


def _keyword_topics(brief: str) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(brief)]
    topics: list[str] = []
    for w in words:
        if w in _STOPWORDS or w in topics:
            continue
        topics.append(w)
    return topics[:6]


def _fallback_criteria(brief: str, geo_playbook: dict) -> SearchCriteria:
    topics = _keyword_topics(brief)
    geo_topics = list(geo_playbook.get("very_strong_signals", []))[:5]
    queries: list[str] = []
    base_topics = topics or ["AI", "marketing"]
    for t in base_topics[:3]:
        queries.append(f"{t} creator instagram")
    for g in geo_topics[:3]:
        queries.append(f"{g} creator")
    queries.append("AI search generative engine optimization creator")
    # dedupe, cap
    seen: set[str] = set()
    unique = [q for q in queries if not (q.lower() in seen or seen.add(q.lower()))]
    return SearchCriteria(
        topics=topics,
        geo_related_topics=geo_topics,
        creator_types=["marketing educator", "technology creator", "founder", "thought leader"],
        search_queries=unique[:_MAX_QUERIES],
    )


async def parse_brief(
    brief: str,
    llm: LLMService,
    geo_playbook: dict,
    max_queries: int,
) -> QueryParseResult:
    warnings: list[str] = []
    try:
        raw = await llm.complete_json(build_brief_parse_messages(brief, geo_playbook))
        criteria = SearchCriteria.model_validate(
            {
                "topics": raw.get("topics", []),
                "geo_related_topics": raw.get("geo_related_topics", []),
                "creator_types": raw.get("creator_types", []),
                "search_queries": raw.get("search_queries", []),
            }
        )
        if not criteria.search_queries:
            raise ValueError("LLM returned no search queries")
        criteria = criteria.model_copy(
            update={"search_queries": _dedupe_queries(criteria.search_queries)[:max_queries]}
        )
        return QueryParseResult(criteria, used_fallback=False, warnings=warnings)
    except (LLMUnavailableError, ValueError) as exc:
        logger.warning("Brief parsing fell back to keywords: %s", exc)
        warnings.append(
            "AI brief understanding was unavailable; used a keyword-based fallback. "
            "Results may be less targeted."
        )
        criteria = _fallback_criteria(brief, geo_playbook)
        criteria = criteria.model_copy(
            update={"search_queries": criteria.search_queries[:max_queries]}
        )
        return QueryParseResult(criteria, used_fallback=True, warnings=warnings)


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        # strip operators the model may still emit; providers scope to Instagram
        s = re.sub(r"\bsite:\S+\s*", "", q, flags=re.IGNORECASE)
        s = s.replace('"', "").strip()
        key = re.sub(r"\s+", " ", s.lower())
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out
