"""Refresh path + display-name extraction from evidence."""
import pytest
from datetime import datetime, timezone

from app.config.settings import get_settings
from app.providers.base import SearchResult
from app.services import search_orchestrator
from app.services.deduplication import Candidate, build_candidates
from app.services.enrichment_service import _guess_display_name, enrich_candidates
from tests.conftest import FakeLLM, FakeProvider

GEO = {"very_strong_signals": [], "summary": "", "related_signals": [],
       "weak_or_generic_signals": [], "negative_signals": [], "ideal_creator_profiles": []}


def _ev(title):
    return SearchResult(provider="tavily", url="https://www.instagram.com/x/", title=title,
                        snippet="AI search", retrieved_at=datetime.now(timezone.utc))


@pytest.mark.parametrize("title,expected", [
    ("Jane Smith (@janesmith) • Instagram photos and videos", "Jane Smith"),
    ("Jason Pantana | Marketing + AI (@jasonpantana) • Instagram", "Jason Pantana"),
    ("Neil Patel (@neilpatel) • Instagram", "Neil Patel"),
    ("someone on Instagram: \"my post\"", "someone"),
    ("Instagram", None),
    ("Login • Instagram", None),
])
def test_display_name_extraction(title, expected):
    cand = Candidate(handle="x", instagram_url="https://www.instagram.com/x/", evidence=[_ev(title)])
    assert _guess_display_name(cand) == expected


@pytest.mark.asyncio
async def test_enrichment_sets_name_and_is_bounded():
    cands = build_candidates([
        SearchResult(provider="tavily", url="https://www.instagram.com/foo/",
                     title="Foo Bar (@foo) • Instagram", snippet="x",
                     retrieved_at=datetime.now(timezone.utc)),
    ])
    warnings = await enrich_candidates(cands, [FakeProvider("keyless")], brief_topics=["AI"])
    assert cands[0].display_name == "Foo Bar"
    assert isinstance(warnings, list)


@pytest.mark.asyncio
async def test_refresh_updates_creator(db_session):
    settings = get_settings()
    profiles = {"*": [("https://www.instagram.com/refreshme/", "Refresh Me (@refreshme)", "AI search SEO")]}
    llm = FakeLLM([
        {"topics": ["AI"], "geo_related_topics": ["AI search"], "creator_types": ["x"],
         "search_queries": ["AI search creator"]},
        {"creators": [{"handle": "refreshme", "geo_search_relevance": 50, "topic_relevance": 50,
                       "content_relevance": 50, "creator_fit": 50, "confidence": 0.6,
                       "relevant_topics": ["AI"], "fit_explanation": "v1", "content_summary": "v1"}]},
        # brief parse for refresh
        {"topics": ["AI"], "geo_related_topics": ["AI search"], "creator_types": ["x"],
         "search_queries": ["AI search creator"]},
        # re-analysis
        {"creators": [{"handle": "refreshme", "geo_search_relevance": 88, "topic_relevance": 80,
                       "content_relevance": 80, "creator_fit": 75, "confidence": 0.85,
                       "relevant_topics": ["AI", "GEO"], "fit_explanation": "v2 stronger",
                       "content_summary": "v2"}]},
    ])
    providers = [FakeProvider("tavily", results_by_query=profiles)]
    resp = await search_orchestrator.run_search(
        db_session, brief="Find AI search creators for GEO", limit=8, force_refresh=True,
        settings=settings, llm=llm, providers=providers, geo_playbook=GEO,
    )
    cid = resp.results[0].id
    old = resp.results[0].score

    refreshed = await search_orchestrator.refresh_creator(
        db_session, creator_id=cid, settings=settings, llm=llm, providers=providers, geo_playbook=GEO,
    )
    assert refreshed is not None
    assert refreshed.creator.score != old
    assert refreshed.creator.explanation == "v2 stronger"


@pytest.mark.asyncio
async def test_refresh_missing_creator_returns_none(db_session):
    settings = get_settings()
    out = await search_orchestrator.refresh_creator(
        db_session, creator_id=424242, settings=settings, llm=FakeLLM(unavailable=True),
        providers=[], geo_playbook=GEO,
    )
    assert out is None
