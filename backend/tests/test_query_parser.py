"""Brief parsing: LLM path + deterministic keyword fallback."""
import pytest

from app.config.settings import get_geo_playbook
from app.services.query_parser import parse_brief
from tests.conftest import FakeLLM

BRIEF = "Find Instagram creators who cover AI, marketing and emerging technology for our GEO Playbook."


@pytest.mark.asyncio
async def test_llm_path_produces_criteria():
    llm = FakeLLM([
        {
            "topics": ["AI", "marketing", "emerging technology"],
            "geo_related_topics": ["AI search", "Generative Engine Optimization"],
            "creator_types": ["marketing educator", "founder"],
            "search_queries": ["AI search marketing creator", "GEO educator instagram",
                               "AI search marketing creator"],  # dup on purpose
        }
    ])
    result = await parse_brief(BRIEF, llm, get_geo_playbook(), max_queries=6)
    assert result.used_fallback is False
    assert "AI" in result.criteria.topics
    # duplicate query removed
    assert len(result.criteria.search_queries) == len(set(q.lower() for q in result.criteria.search_queries))
    assert result.criteria.search_queries


@pytest.mark.asyncio
async def test_fallback_when_llm_unavailable():
    llm = FakeLLM(unavailable=True)
    result = await parse_brief(BRIEF, llm, get_geo_playbook(), max_queries=6)
    assert result.used_fallback is True
    assert result.warnings
    assert result.criteria.search_queries          # still produced something
    assert result.criteria.topics


@pytest.mark.asyncio
async def test_fallback_when_llm_returns_no_queries():
    llm = FakeLLM([{"topics": ["AI"], "geo_related_topics": [], "creator_types": [], "search_queries": []}])
    result = await parse_brief(BRIEF, llm, get_geo_playbook(), max_queries=6)
    assert result.used_fallback is True


@pytest.mark.asyncio
async def test_query_cap_enforced():
    llm = FakeLLM([
        {
            "topics": ["AI"],
            "geo_related_topics": ["GEO"],
            "creator_types": ["educator"],
            "search_queries": [f"query number {i}" for i in range(30)],
        }
    ])
    result = await parse_brief(BRIEF, llm, get_geo_playbook(), max_queries=6)
    assert len(result.criteria.search_queries) <= 6
