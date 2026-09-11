"""End-to-end search orchestration: brief -> criteria -> discovery -> enrichment
-> LLM analysis -> deterministic scoring -> ranking -> persistence."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.db_models import Creator, CreatorAnalysis
from app.models.schemas import (
    CreatorResult,
    DataStatus,
    LLMCreatorAnalysis,
    RefreshResponse,
    SearchCriteria,
    SearchResponse,
)
from app.providers.base import SearchProvider
from app.providers.instagram_url import handle_to_url
from app.services import creator_service
from app.services.analysis_service import analyze_candidates
from app.services.deduplication import Candidate
from app.services.discovery_service import discover_candidates
from app.services.enrichment_service import enrich_candidates
from app.services.llm_service import LLMService
from app.services.query_parser import parse_brief
from app.services.scoring_service import calculate_relevance_score

logger = logging.getLogger(__name__)


def normalize_brief(brief: str) -> str:
    return re.sub(r"\s+", " ", brief.strip().lower())


def _clamp_limit(requested: int | None, settings: Settings) -> int:
    value = requested or settings.default_result_limit
    return max(settings.min_result_limit, min(settings.max_result_limit, value))


def _discovery_queries(criteria: SearchCriteria, cap: int) -> list[str]:
    """Build the discovery query set, prioritizing COMBINED-intent queries.

    A brief like "AI + marketing" should search for "AI marketing instagram
    creator", not spend most of the budget on a generic "AI instagram creator"
    query that surfaces unrelated AI-education accounts. Combined queries
    (topic+topic, GEO+topic) go first; single-topic/GEO queries and any
    leftover LLM-generated queries only fill remaining slots. Everything here
    is built dynamically from `criteria` — nothing is a hardcoded phrase.
    The final list is capped at `cap` (settings.max_search_queries) so a
    search never issues more discovery requests than configured.
    """
    topics = criteria.topics
    geo = criteria.geo_related_topics
    llm_queries = list(criteria.search_queries)

    def combo(*parts: str) -> str:
        return " ".join(p for p in parts if p) + " instagram creator"

    # Priority 1-3, 5-6: combined-intent queries (topic+topic, GEO+topic).
    combined: list[str] = []
    if len(topics) >= 2:
        combined.append(combo(topics[0], topics[1]))
    if geo and topics:
        combined.append(combo(geo[0], topics[0]))
    if len(topics) >= 3:
        combined.append(combo(topics[0], topics[2]))
    elif len(topics) >= 2:
        combined.append(combo(topics[1], topics[0]))
    if len(geo) >= 2 and topics:
        combined.append(combo(geo[1], topics[0]))
    elif geo and len(topics) >= 2:
        combined.append(combo(geo[0], topics[1]))
    if len(topics) >= 2 and geo:
        combined.append(combo(topics[1], geo[0]))

    # Priority 4: one LLM-generated (typically already multi-concept) query,
    # inserted after the first couple of combined queries.
    if llm_queries:
        combined.insert(min(2, len(combined)), llm_queries[0])

    # Fallback filler for briefs too thin to fill the cap with combined
    # queries alone (e.g. a single-topic brief) — single-concept queries and
    # any remaining LLM queries.
    filler: list[str] = [combo(t) for t in topics]
    filler.extend(combo(g) for g in geo)
    filler.extend(llm_queries[1:])

    ordered = combined + filler
    seen: set[str] = set()
    unique: list[str] = []
    for q in ordered:
        key = re.sub(r"\s+", " ", q.strip().lower())
        if key and key not in seen:
            seen.add(key)
            unique.append(q.strip())
    # Hard cap: a search must never issue more discovery queries than configured.
    return unique[:cap]


def _score_and_rank(
    db: Session,
    candidates: list[Candidate],
    analyses: dict[str, LLMCreatorAnalysis],
    run,
    brief: str,
) -> list[tuple[Creator, CreatorAnalysis]]:
    """Deterministic score for every analyzed candidate, then rank descending."""
    scored: list[tuple[Creator, CreatorAnalysis, int]] = []
    for cand in candidates:
        analysis = analyses.get(cand.handle)
        if analysis is None:
            continue
        overall = calculate_relevance_score(
            analysis.geo_search_relevance,
            analysis.topic_relevance,
            analysis.content_relevance,
            analysis.creator_fit,
        )
        creator = creator_service.upsert_creator(db, cand, analysis)
        row = creator_service.save_analysis(db, creator, run, brief, analysis, overall)
        creator_service.link_analysis_evidence(
            db, row, creator, cand, analysis.evidence_indices
        )
        scored.append((creator, row, overall))
    scored.sort(key=lambda t: t[2], reverse=True)
    return [(c, a) for c, a, _ in scored]


def _apply_relevance_gate(
    ranked: list[tuple[Creator, CreatorAnalysis]],
    settings: Settings,
) -> tuple[list[tuple[Creator, CreatorAnalysis]], list[str]]:
    """A creator only makes the shortlist if it clears BOTH credibility
    thresholds. This does not touch the 35/30/25/10 weighting formula — it
    filters *after* the deterministic score is computed. Weak matches are
    excluded outright; the shortlist is never padded back up to
    `min_result_limit` with profiles that failed the gate. `ranked` is
    already sorted descending, so `eligible` preserves that order.
    """
    eligible = [
        (creator, analysis)
        for creator, analysis in ranked
        if analysis.overall_score >= settings.min_relevance_score
        and analysis.confidence >= settings.min_result_confidence
    ]
    warnings: list[str] = []
    if ranked and not eligible:
        warnings.append(
            "No creators met the relevance threshold for this brief. "
            "Try a more specific brief."
        )
    return eligible, warnings


async def run_search(
    db: Session,
    *,
    brief: str,
    limit: int | None,
    force_refresh: bool,
    settings: Settings,
    llm: LLMService,
    providers: list[SearchProvider],
    geo_playbook: dict,
) -> SearchResponse:
    normalized = normalize_brief(brief)
    result_limit = _clamp_limit(limit, settings)
    warnings: list[str] = []

    # 1. Fresh cache hit for an identical brief
    if not force_refresh:
        cached = creator_service.find_cached_run(db, normalized, settings.cache_ttl_hours)
        if cached:
            results = creator_service.load_run_results(db, cached, "cached")[:result_limit]
            if results:
                logger.info("Serving cached run %s for %r", cached.id, normalized)
                return SearchResponse(
                    brief=brief,
                    criteria=SearchCriteria.model_validate(
                        json.loads(cached.criteria_json or "{}")
                    ),
                    results=results,
                    candidate_count=cached.candidate_count,
                    returned_count=len(results),
                    data_status="cached",
                    warnings=["Showing cached results from a recent identical search."],
                )

    # 2. Understand the brief (LLM, with keyword fallback)
    parsed = await parse_brief(brief, llm, geo_playbook, settings.max_search_queries)
    criteria = parsed.criteria
    warnings.extend(parsed.warnings)

    run = creator_service.create_search_run(db, brief, normalized, criteria.model_dump_json())

    # 3. Discover candidates across providers
    discovery = await discover_candidates(
        providers,
        _discovery_queries(criteria, settings.max_search_queries),
        max_candidates=settings.max_candidates,
        per_query_limit=12,
    )
    warnings.extend(discovery.provider_errors)

    if not discovery.candidates:
        stale = _try_stale_cache(db, normalized)
        if stale:
            return stale
        no_hit = warnings + ["No Instagram creators were found for this brief."]
        run.candidate_count = 0
        run.returned_count = 0
        run.data_status = "partial"
        run.warnings_json = json.dumps(no_hit)
        db.commit()
        return SearchResponse(
            brief=brief,
            criteria=criteria,
            results=[],
            candidate_count=0,
            returned_count=0,
            data_status="partial",
            warnings=no_hit,
        )

    # Cap how many candidates go to the LLM (token/cost budget). Discovery
    # order already front-loads the most on-topic queries.
    analysis_candidates = discovery.candidates[: settings.max_analysis_candidates]

    # 4. Enrich evidence
    warnings.extend(
        await enrich_candidates(analysis_candidates, providers, brief_topics=criteria.topics)
    )

    # 5. LLM batched analysis
    analysis_outcome = await analyze_candidates(
        brief, criteria, geo_playbook, analysis_candidates, llm
    )
    warnings.extend(analysis_outcome.warnings)

    if analysis_outcome.failed:
        stale = _try_stale_cache(db, normalized)
        if stale:
            return stale

    # 6. Deterministic score + rank + credibility gate + persist
    ranked = _score_and_rank(db, analysis_candidates, analysis_outcome.analyses, run, brief)
    eligible, gate_warnings = _apply_relevance_gate(ranked, settings)
    warnings.extend(gate_warnings)
    creator_service.record_result_rows(db, run, eligible[:result_limit])

    data_status: DataStatus = "live"
    if parsed.used_fallback or discovery.provider_errors or analysis_outcome.warnings:
        data_status = "partial"

    results: list[CreatorResult] = [
        creator_service.to_creator_result(creator, analysis, data_status)
        for creator, analysis in eligible[:result_limit]
    ]

    if 0 < len(results) < settings.min_result_limit:
        warnings.append(
            f"Only {len(results)} creator(s) met the relevance threshold - fewer than the "
            f"target of {settings.min_result_limit}. Weak matches were excluded rather than "
            "added to the shortlist."
        )

    run.candidate_count = len(discovery.candidates)
    run.returned_count = len(results)
    run.data_status = data_status
    run.warnings_json = json.dumps(warnings)
    db.commit()

    return SearchResponse(
        brief=brief,
        criteria=criteria,
        results=results,
        candidate_count=len(discovery.candidates),
        returned_count=len(results),
        data_status=data_status,
        warnings=warnings,
    )


def _try_stale_cache(db: Session, normalized: str) -> SearchResponse | None:
    """Live path produced nothing: fall back to any prior real run, labelled cached."""
    run = creator_service.find_cached_run(db, normalized, ttl_hours=24 * 365)
    if not run:
        return None
    results = creator_service.load_run_results(db, run, "cached")
    if not results:
        return None
    logger.info("Live search empty; serving stale cached run %s", run.id)
    return SearchResponse(
        brief=run.brief,
        criteria=SearchCriteria.model_validate(json.loads(run.criteria_json or "{}")),
        results=results,
        candidate_count=run.candidate_count,
        returned_count=len(results),
        data_status="cached",
        warnings=[
            "Live discovery is unavailable right now; showing the most recent "
            "previously retrieved real results (cached)."
        ],
    )


async def refresh_creator(
    db: Session,
    *,
    creator_id: int,
    settings: Settings,
    llm: LLMService,
    providers: list[SearchProvider],
    geo_playbook: dict,
) -> RefreshResponse | None:
    creator = db.get(Creator, creator_id)
    if creator is None:
        return None

    prev = creator_service.latest_analysis_for_creator(db, creator_id)
    brief = (
        prev.brief
        if prev and prev.brief
        else f"Instagram creator @{creator.handle} and GEO relevance"
    )

    parsed = await parse_brief(brief, llm, geo_playbook, settings.max_search_queries)
    criteria = parsed.criteria

    topic_hint = " ".join(criteria.topics[:3]) or "AI search marketing"
    name_hint = creator.display_name or creator.handle
    queries = [
        f"{creator.handle} instagram creator",
        f"{name_hint} {topic_hint} instagram",
    ]
    discovery = await discover_candidates(
        providers, queries, max_candidates=settings.max_candidates, per_query_limit=6
    )
    warnings: list[str] = list(discovery.provider_errors)

    target = next((c for c in discovery.candidates if c.handle == creator.handle), None)
    if target is None:
        target = Candidate(handle=creator.handle, instagram_url=handle_to_url(creator.handle))

    await enrich_candidates([target], providers, brief_topics=criteria.topics)

    # Seed the refresh analysis with the creator's existing evidence so a refresh
    # never scores against nothing when targeted re-discovery misses the handle.
    # Newly discovered evidence (if any) is kept alongside it.
    _merge_stored_evidence(target, creator)
    if not target.evidence:
        warnings.append("No fresh evidence was found; re-analyzed against existing evidence.")

    outcome = await analyze_candidates(brief, criteria, geo_playbook, [target], llm)
    warnings.extend(outcome.warnings)
    analysis = outcome.analyses.get(creator.handle)

    if analysis is None:
        fallback_row = prev or _placeholder_analysis(creator)
        return RefreshResponse(
            creator=creator_service.to_creator_result(creator, fallback_row, "partial"),
            warnings=warnings
            + ["Refresh could not produce a new analysis; showing the previous one."],
        )

    overall = calculate_relevance_score(
        analysis.geo_search_relevance,
        analysis.topic_relevance,
        analysis.content_relevance,
        analysis.creator_fit,
    )
    creator = creator_service.upsert_creator(db, target, analysis)
    row = creator_service.save_analysis(db, creator, None, brief, analysis, overall)
    creator_service.link_analysis_evidence(
        db, row, creator, target, analysis.evidence_indices
    )
    db.commit()

    status: DataStatus = "partial" if warnings or parsed.used_fallback else "live"
    return RefreshResponse(
        creator=creator_service.to_creator_result(creator, row, status),
        warnings=warnings,
    )


def _merge_stored_evidence(target: Candidate, creator: Creator) -> None:
    """Add the creator's already-stored CreatorEvidence to `target` as
    SearchResults, without duplicating anything discovery just found."""
    from app.providers.base import SearchResult

    seen = {e.url for e in target.evidence}
    for row in creator.evidence:
        if row.source_url in seen:
            continue
        retrieved = row.retrieved_at
        if retrieved is not None and retrieved.tzinfo is None:
            retrieved = retrieved.replace(tzinfo=timezone.utc)
        target.evidence.append(
            SearchResult(
                provider=row.provider,
                url=row.source_url,
                title=row.title,
                snippet=row.snippet,
                retrieved_at=retrieved or datetime.now(timezone.utc),
                synthetic=row.synthetic,
            )
        )
        seen.add(row.source_url)


def _placeholder_analysis(creator: Creator) -> CreatorAnalysis:
    return CreatorAnalysis(
        creator_id=creator.id,
        brief="",
        geo_search_relevance=0,
        topic_relevance=0,
        content_relevance=0,
        creator_fit=0,
        overall_score=0,
        created_at=creator.created_at,
    )
