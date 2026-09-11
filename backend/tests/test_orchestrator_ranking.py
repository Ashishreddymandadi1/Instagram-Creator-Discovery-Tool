"""End-to-end orchestration with fakes: ranking, limit clamp, no fabricated padding."""
import pytest

from app.config.settings import get_settings
from app.services import search_orchestrator
from tests.conftest import FakeLLM, FakeProvider

BRIEF = "Find Instagram creators covering AI search and GEO."

PROFILES = {
    "*": [
        (f"https://www.instagram.com/creator{i}/", f"Creator {i} (@creator{i})", "AI search SEO")
        for i in range(9)
    ]
}


def _analysis_row(handle, geo):
    return {
        "handle": handle, "name": None, "relevant_topics": ["AI search"], "geo_concepts": ["GEO"],
        "content_summary": "evidence-based", "geo_search_relevance": geo, "topic_relevance": 60,
        "content_relevance": 60, "creator_fit": 60, "fit_explanation": "ok",
        "evidence_indices": [0], "confidence": 0.7, "warnings": [],
    }


@pytest.mark.asyncio
async def test_results_ranked_desc_and_limited(db_session):
    settings = get_settings()
    llm = FakeLLM([
        {"topics": ["AI"], "geo_related_topics": ["AI search"], "creator_types": ["educator"],
         "search_queries": ["AI search creator"]},
        {"creators": [_analysis_row(f"creator{i}", geo=10 * i) for i in range(9)]},
    ])
    providers = [FakeProvider("tavily", results_by_query=PROFILES)]

    resp = await search_orchestrator.run_search(
        db_session, brief=BRIEF, limit=8, force_refresh=True, settings=settings,
        llm=llm, providers=providers, geo_playbook={"very_strong_signals": [], "summary": ""},
    )
    scores = [r.score for r in resp.results]
    assert scores == sorted(scores, reverse=True)
    assert 5 <= len(resp.results) <= 10
    assert resp.returned_count == len(resp.results)
    assert resp.data_status in {"live", "partial"}
    # top creator is the one with highest geo signal (creator8)
    assert resp.results[0].handle == "@creator8"


@pytest.mark.asyncio
async def test_few_candidates_not_padded(db_session):
    settings = get_settings()
    llm = FakeLLM([
        {"topics": ["AI"], "geo_related_topics": ["AI search"], "creator_types": ["x"],
         "search_queries": ["AI search creator"]},
        {"creators": [_analysis_row("creator0", 90), _analysis_row("creator1", 80)]},
    ])
    two = {"*": [
        ("https://www.instagram.com/creator0/", "Creator 0 (@creator0)", "AI search"),
        ("https://www.instagram.com/creator1/", "Creator 1 (@creator1)", "AI search"),
    ]}
    providers = [FakeProvider("tavily", results_by_query=two)]
    resp = await search_orchestrator.run_search(
        db_session, brief=BRIEF, limit=8, force_refresh=True, settings=settings,
        llm=llm, providers=providers, geo_playbook={"very_strong_signals": [], "summary": ""},
    )
    assert len(resp.results) == 2
    assert any("fewer than the target" in w for w in resp.warnings)


@pytest.mark.asyncio
async def test_limit_clamped_to_max_10(db_session):
    settings = get_settings()
    llm = FakeLLM([
        {"topics": ["AI"], "geo_related_topics": [], "creator_types": [],
         "search_queries": ["AI search creator"]},
        {"creators": [_analysis_row(f"creator{i}", 50) for i in range(9)]},
    ])
    providers = [FakeProvider("tavily", results_by_query=PROFILES)]
    resp = await search_orchestrator.run_search(
        db_session, brief=BRIEF, limit=999, force_refresh=True, settings=settings,
        llm=llm, providers=providers, geo_playbook={"very_strong_signals": [], "summary": ""},
    )
    assert len(resp.results) <= 10
