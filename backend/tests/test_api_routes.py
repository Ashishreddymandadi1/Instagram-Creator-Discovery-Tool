"""API routes via TestClient with dependency overrides (no network)."""
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import (
    get_app_settings,
    get_geo_context,
    get_llm_service,
    get_search_providers,
)
from app.main import app
from app.config.settings import Settings
from tests.conftest import FakeLLM, FakeProvider

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.db_models import Base


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across TestClient's threads
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def _db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    profiles = {"*": [
        (f"https://www.instagram.com/creator{i}/", f"Creator {i} (@creator{i})", "AI search SEO")
        for i in range(6)
    ]}
    llm = FakeLLM([
        {"topics": ["AI"], "geo_related_topics": ["AI search"], "creator_types": ["educator"],
         "search_queries": ["AI search creator"]},
        {"creators": [
            {"handle": f"creator{i}", "geo_search_relevance": 70 - i, "topic_relevance": 60,
             "content_relevance": 60, "creator_fit": 60, "confidence": 0.7,
             "relevant_topics": ["AI search"], "geo_concepts": ["GEO"], "fit_explanation": "ok",
             "content_summary": "evidence"} for i in range(6)
        ]},
    ])

    app.dependency_overrides[get_db] = _db
    # Every provider key set explicitly (even to "") so this test is deterministic
    # regardless of what real keys happen to be in a developer's local backend/.env.
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        anthropic_api_key="test", tavily_api_key="test", serper_api_key="", brave_api_key="",
        search_providers="tavily",
    )
    app.dependency_overrides[get_llm_service] = lambda: llm
    app.dependency_overrides[get_search_providers] = lambda: [FakeProvider("tavily", results_by_query=profiles)]
    app.dependency_overrides[get_geo_context] = lambda: {"very_strong_signals": [], "summary": ""}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_reports_booleans_not_keys(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["llm_configured"] is True
    assert "anthropic_api_key" not in str(body)
    # Default demo config: Tavily only, no key values ever exposed.
    assert body["search_providers"] == ["tavily"]
    assert "test" not in str(body)  # the fake key value must not leak


def test_search_returns_ranked_shortlist(client):
    r = client.post("/api/search", json={"brief": "Find AI search creators for our GEO Playbook", "limit": 8})
    assert r.status_code == 200
    body = r.json()
    scores = [x["score"] for x in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert body["results"][0]["instagram_url"].startswith("https://www.instagram.com/")
    for x in body["results"]:
        assert x["evidence"]
        assert x["follower_count"] is None
        assert set(x["score_breakdown"]) == {
            "geo_search_relevance", "topic_relevance", "content_relevance", "creator_fit"
        }


def test_search_rejects_too_short_brief(client):
    assert client.post("/api/search", json={"brief": "hi"}).status_code == 422


def test_creator_fetch_and_refresh(client):
    body = client.post("/api/search", json={"brief": "Find AI search creators for our GEO Playbook"}).json()
    cid = body["results"][0]["id"]
    got = client.get(f"/api/creators/{cid}")
    assert got.status_code == 200 and got.json()["id"] == cid
    assert client.get("/api/creators/999999").status_code == 404


def test_error_messages_do_not_leak_internals(client):
    app.dependency_overrides[get_search_providers] = lambda: []
    r = client.post("/api/search", json={"brief": "Find AI creators for GEO outreach"})
    assert r.status_code == 503
    assert "Traceback" not in r.text and "ANTHROPIC_API_KEY=" not in r.text
