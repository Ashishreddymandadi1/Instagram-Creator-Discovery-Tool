"""Persistence + mapping between DB rows and API schemas."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.db_models import (
    AnalysisEvidence,
    Creator,
    CreatorAnalysis,
    CreatorEvidence,
    SearchResult as SearchResultRow,
    SearchRun,
)
from app.models.schemas import (
    CreatorResult,
    DataStatus,
    Evidence,
    LLMCreatorAnalysis,
    ScoreBreakdown,
)
from app.services.deduplication import (
    MAX_EVIDENCE_PER_ANALYSIS,
    Candidate,
    resolve_evidence_indices,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime:
    if dt is None:
        return _utcnow()
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────
# Upserts
# ─────────────────────────────────────────────────────────────
def upsert_creator(db: Session, candidate: Candidate, analysis: LLMCreatorAnalysis) -> Creator:
    creator = db.scalar(select(Creator).where(Creator.handle == candidate.handle))
    if creator is None:
        creator = Creator(handle=candidate.handle, instagram_url=candidate.instagram_url)
        db.add(creator)
    creator.instagram_url = candidate.instagram_url
    creator.display_name = analysis.name or candidate.display_name or creator.display_name
    creator.summary = (
        analysis.content_summary
        if analysis.content_summary and analysis.content_summary != "Not available"
        else creator.summary
    )
    creator.topics_json = json.dumps(analysis.relevant_topics)
    creator.geo_concepts_json = json.dumps(analysis.geo_concepts)
    creator.last_enriched_at = _utcnow()
    db.flush()
    _replace_evidence(db, creator, candidate)
    return creator


def _replace_evidence(db: Session, creator: Creator, candidate: Candidate) -> None:
    existing = {e.source_url for e in creator.evidence}
    for ev in candidate.evidence:
        if ev.url in existing:
            continue
        # append via the relationship so creator.evidence is current in-session
        creator.evidence.append(
            CreatorEvidence(
                provider=ev.provider,
                source_url=ev.url,
                title=ev.title,
                snippet=ev.snippet,
                synthetic=ev.synthetic,
                retrieved_at=_aware(ev.retrieved_at),
            )
        )
        existing.add(ev.url)
    db.flush()


def save_analysis(
    db: Session,
    creator: Creator,
    run: SearchRun | None,
    brief: str,
    analysis: LLMCreatorAnalysis,
    overall_score: int,
) -> CreatorAnalysis:
    row = CreatorAnalysis(
        creator_id=creator.id,
        search_run_id=run.id if run else None,
        brief=brief,
        geo_search_relevance=analysis.geo_search_relevance,
        topic_relevance=analysis.topic_relevance,
        content_relevance=analysis.content_relevance,
        creator_fit=analysis.creator_fit,
        overall_score=overall_score,
        content_summary=analysis.content_summary or "Not available",
        explanation=analysis.fit_explanation or "Not available",
        relevant_topics_json=json.dumps(analysis.relevant_topics),
        geo_concepts_json=json.dumps(analysis.geo_concepts),
        confidence=analysis.confidence,
        warnings_json=json.dumps(analysis.warnings),
    )
    db.add(row)
    db.flush()
    return row


def link_analysis_evidence(
    db: Session,
    analysis: CreatorAnalysis,
    creator: Creator,
    candidate: Candidate,
    evidence_indices: list[int],
) -> None:
    """Associate `analysis` with the exact CreatorEvidence rows that supported it.

    Only the first MAX_EVIDENCE_PER_ANALYSIS items of the candidate were shown to
    the LLM (indexed 0..n-1), so `evidence_indices` are validated against that set.
    If no valid index survives, fall back conservatively to *all* evidence that
    was supplied to this analysis — never to unrelated historical evidence.
    """
    sent = candidate.evidence[:MAX_EVIDENCE_PER_ANALYSIS]
    if not sent:
        return

    valid = resolve_evidence_indices(evidence_indices, len(sent))
    chosen = [sent[i] for i in valid] if valid else sent

    url_to_row = {e.source_url: e for e in creator.evidence}
    linked_ids: set[int] = set()
    for result in chosen:
        row = url_to_row.get(result.url)
        if row is None or row.id in linked_ids:
            continue
        linked_ids.add(row.id)
        db.add(AnalysisEvidence(analysis_id=analysis.id, evidence_id=row.id))
    db.flush()


# ─────────────────────────────────────────────────────────────
# Mapping to API schema
# ─────────────────────────────────────────────────────────────
def _evidence_models(rows: list[CreatorEvidence]) -> list[Evidence]:
    return [
        Evidence(
            source_provider=e.provider,
            source_url=e.source_url,
            title=e.title,
            snippet=e.snippet,
            retrieved_at=_aware(e.retrieved_at),
            synthetic=e.synthetic,
        )
        for e in sorted(rows, key=lambda x: _aware(x.retrieved_at), reverse=True)
    ]


def _analysis_scoped_evidence(analysis: CreatorAnalysis) -> list[CreatorEvidence]:
    """Evidence linked to THIS analysis only (search-specific provenance)."""
    seen: set[int] = set()
    rows: list[CreatorEvidence] = []
    for link in analysis.evidence_links:
        ev = link.evidence
        if ev is not None and ev.id not in seen:
            seen.add(ev.id)
            rows.append(ev)
    return rows


def to_creator_result(
    creator: Creator,
    analysis: CreatorAnalysis,
    data_status: DataStatus,
) -> CreatorResult:
    return CreatorResult(
        id=creator.id,
        name=creator.display_name,
        handle=f"@{creator.handle}",
        instagram_url=creator.instagram_url,
        relevant_topics=json.loads(analysis.relevant_topics_json or "[]"),
        geo_concepts=json.loads(analysis.geo_concepts_json or "[]"),
        content_summary=analysis.content_summary or "Not available",
        bio_or_summary=creator.summary,
        score=analysis.overall_score,
        score_breakdown=ScoreBreakdown(
            geo_search_relevance=round(analysis.geo_search_relevance),
            topic_relevance=round(analysis.topic_relevance),
            content_relevance=round(analysis.content_relevance),
            creator_fit=round(analysis.creator_fit),
        ),
        explanation=analysis.explanation or "Not available",
        confidence=analysis.confidence,
        data_status=data_status,
        last_updated=_aware(analysis.created_at),
        evidence=_evidence_models(_analysis_scoped_evidence(analysis)),
        warnings=json.loads(analysis.warnings_json or "[]"),
    )


# ─────────────────────────────────────────────────────────────
# Search-run persistence + cached replay
# ─────────────────────────────────────────────────────────────
def create_search_run(db: Session, brief: str, normalized_brief: str, criteria_json: str) -> SearchRun:
    run = SearchRun(brief=brief, normalized_brief=normalized_brief, criteria_json=criteria_json)
    db.add(run)
    db.flush()
    return run


def record_result_rows(db: Session, run: SearchRun, ranked: list[tuple[Creator, CreatorAnalysis]]) -> None:
    for rank, (creator, analysis) in enumerate(ranked, start=1):
        db.add(
            SearchResultRow(
                search_run_id=run.id,
                creator_id=creator.id,
                analysis_id=analysis.id,
                rank=rank,
            )
        )
    db.flush()


def find_cached_run(db: Session, normalized_brief: str, ttl_hours: float) -> SearchRun | None:
    cutoff = _utcnow() - timedelta(hours=ttl_hours)
    run = db.scalar(
        select(SearchRun)
        .where(SearchRun.normalized_brief == normalized_brief)
        .where(SearchRun.returned_count > 0)
        .order_by(SearchRun.created_at.desc())
    )
    if run and _aware(run.created_at) >= cutoff:
        return run
    return None


def load_run_results(db: Session, run: SearchRun, data_status: DataStatus) -> list[CreatorResult]:
    rows = db.scalars(
        select(SearchResultRow)
        .where(SearchResultRow.search_run_id == run.id)
        .order_by(SearchResultRow.rank)
    ).all()
    out: list[CreatorResult] = []
    for row in rows:
        creator = db.get(Creator, row.creator_id)
        analysis = db.get(CreatorAnalysis, row.analysis_id)
        if creator and analysis:
            out.append(to_creator_result(creator, analysis, data_status))
    return out


def latest_analysis_for_creator(db: Session, creator_id: int) -> CreatorAnalysis | None:
    return db.scalar(
        select(CreatorAnalysis)
        .where(CreatorAnalysis.creator_id == creator_id)
        .order_by(CreatorAnalysis.created_at.desc())
    )
