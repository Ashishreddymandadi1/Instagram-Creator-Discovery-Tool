"""Data-quality rule: missing values are never invented."""
import json
from datetime import datetime, timezone

from app.models.schemas import CreatorResult, LLMCreatorAnalysis
from app.providers.base import SearchResult
from app.services.creator_service import (
    link_analysis_evidence,
    save_analysis,
    to_creator_result,
    upsert_creator,
)
from app.services.deduplication import build_candidates
from app.services.scoring_service import calculate_relevance_score


def test_no_follower_or_engagement_fields_fabricated(db_session):
    candidate = build_candidates([
        SearchResult(provider="tavily", url="https://www.instagram.com/nameless/",
                     title="something on Instagram", snippet="no name here",
                     retrieved_at=datetime.now(timezone.utc))
    ])[0]
    analysis = LLMCreatorAnalysis(
        handle="nameless", name=None, relevant_topics=["AI"], geo_concepts=[],
        content_summary="Not available", geo_search_relevance=40, topic_relevance=50,
        content_relevance=30, creator_fit=45, fit_explanation="thin evidence",
        confidence=0.3, warnings=["low confidence"],
    )
    creator = upsert_creator(db_session, candidate, analysis)
    overall = calculate_relevance_score(40, 50, 30, 45)
    row = save_analysis(db_session, creator, None, "brief", analysis, overall)
    link_analysis_evidence(db_session, row, creator, candidate, analysis.evidence_indices)
    db_session.commit()

    result: CreatorResult = to_creator_result(creator, row, "live")
    assert result.follower_count is None
    assert result.engagement_rate is None
    assert result.verified is None
    assert result.location is None
    assert result.name is None                 # not invented from a bad title
    assert result.content_summary == "Not available"
    assert result.evidence and result.evidence[0].source_url


def test_schema_has_no_random_defaults():
    dumped = CreatorResult.model_json_schema()
    props = dumped["properties"]
    for field in ("follower_count", "engagement_rate", "verified", "location"):
        assert "default" not in props[field] or props[field]["default"] is None
