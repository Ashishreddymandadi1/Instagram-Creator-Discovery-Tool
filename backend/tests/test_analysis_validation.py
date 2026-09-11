"""Malformed / partial LLM analysis output must not crash; bad rows are dropped."""
import pytest

from app.config.settings import get_geo_playbook
from app.models.schemas import SearchCriteria
from app.services.analysis_service import analyze_candidates
from app.providers.base import SearchResult
from app.services.deduplication import build_candidates
from tests.conftest import FakeLLM
from datetime import datetime, timezone

CRITERIA = SearchCriteria(topics=["AI", "marketing"], geo_related_topics=["AI search"])


def _candidates():
    return build_candidates([
        SearchResult(provider="tavily", url="https://www.instagram.com/alpha/",
                     title="Alpha (@alpha)", snippet="AI search educator",
                     retrieved_at=datetime.now(timezone.utc)),
        SearchResult(provider="tavily", url="https://www.instagram.com/beta/",
                     title="Beta (@beta)", snippet="marketing",
                     retrieved_at=datetime.now(timezone.utc)),
    ])


@pytest.mark.asyncio
async def test_malformed_json_marks_failed_not_crash():
    llm = FakeLLM(unavailable=True)
    outcome = await analyze_candidates("brief", CRITERIA, get_geo_playbook(), _candidates(), llm)
    assert outcome.failed is True
    assert outcome.analyses == {}
    assert outcome.warnings


@pytest.mark.asyncio
async def test_partial_batch_keeps_valid_rows_drops_bad():
    llm = FakeLLM([{
        "creators": [
            {"handle": "alpha", "geo_search_relevance": 80, "topic_relevance": 70,
             "content_relevance": 75, "creator_fit": 60, "confidence": 0.8,
             "relevant_topics": ["AI search"], "fit_explanation": "ok"},
            {"handle": "beta", "geo_search_relevance": "not a number"},  # invalid -> clamped to 0, still valid
            {"nonsense": True},                                          # no handle -> dropped
            "totally not a dict",                                        # dropped
        ]
    }])
    outcome = await analyze_candidates("brief", CRITERIA, get_geo_playbook(), _candidates(), llm)
    assert outcome.failed is False
    assert "alpha" in outcome.analyses
    assert outcome.analyses["alpha"].geo_search_relevance == 80
    # beta survived (bad score coerced to 0)
    assert outcome.analyses["beta"].geo_search_relevance == 0


@pytest.mark.asyncio
async def test_unknown_handles_ignored():
    llm = FakeLLM([{"creators": [
        {"handle": "ghost", "geo_search_relevance": 90, "topic_relevance": 90,
         "content_relevance": 90, "creator_fit": 90, "confidence": 0.9},
    ]}])
    outcome = await analyze_candidates("brief", CRITERIA, get_geo_playbook(), _candidates(), llm)
    assert "ghost" not in outcome.analyses
