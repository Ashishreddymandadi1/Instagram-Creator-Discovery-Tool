"""Credibility/relevance gate: a creator must clear both thresholds to make
the shortlist, and combined-intent discovery queries are prioritized."""
import pytest

from app.config.settings import get_settings
from app.services import search_orchestrator
from app.services.search_orchestrator import _apply_relevance_gate, _discovery_queries
from app.models.schemas import SearchCriteria
from tests.conftest import FakeLLM, FakeProvider

GEO = {"summary": "", "very_strong_signals": [], "related_signals": [],
       "weak_or_generic_signals": [], "negative_signals": [], "ideal_creator_profiles": []}


def _criteria(queries=("q1",)):
    return {"topics": ["AI"], "geo_related_topics": ["AI search"],
            "creator_types": ["educator"], "search_queries": list(queries)}


def _row(handle, score, confidence, **overrides):
    row = {"handle": handle, "geo_search_relevance": score, "topic_relevance": score,
           "content_relevance": score, "creator_fit": score, "confidence": confidence,
           "relevant_topics": ["AI"], "fit_explanation": "ok", "content_summary": "ok"}
    row.update(overrides)
    return row


class _FakeAnalysis:
    def __init__(self, overall_score, confidence):
        self.overall_score = overall_score
        self.confidence = confidence


async def _run(db, evidence, groq_responses, limit=8):
    settings = get_settings()
    return await search_orchestrator.run_search(
        db, brief="Find AI marketing creators for GEO", limit=limit, force_refresh=True,
        settings=settings, llm=FakeLLM(groq_responses),
        providers=[FakeProvider("serper", results_by_query={"*": evidence})],
        geo_playbook=GEO,
    )


# ── Unit tests for the gate itself ──────────────────────────────────────────
def test_low_score_excluded():
    settings = get_settings()
    ranked = [("creatorA", _FakeAnalysis(overall_score=20, confidence=0.9))]
    eligible, warnings = _apply_relevance_gate(ranked, settings)
    assert eligible == []
    assert "No creators met the relevance threshold" in warnings[0]


def test_low_confidence_excluded():
    settings = get_settings()
    ranked = [("creatorA", _FakeAnalysis(overall_score=90, confidence=0.1))]
    eligible, _ = _apply_relevance_gate(ranked, settings)
    assert eligible == []


def test_strong_score_and_confidence_included():
    settings = get_settings()
    ranked = [("creatorA", _FakeAnalysis(overall_score=60, confidence=0.5))]
    eligible, warnings = _apply_relevance_gate(ranked, settings)
    assert eligible == ranked
    assert warnings == []


def test_gate_preserves_descending_order():
    settings = get_settings()
    ranked = [
        ("top", _FakeAnalysis(overall_score=80, confidence=0.8)),
        ("mid", _FakeAnalysis(overall_score=60, confidence=0.6)),
        ("weak", _FakeAnalysis(overall_score=10, confidence=0.9)),  # fails score gate
    ]
    eligible, _ = _apply_relevance_gate(ranked, settings)
    assert [c for c, _ in eligible] == ["top", "mid"]


def test_no_ranked_candidates_produces_no_gate_warning():
    settings = get_settings()
    eligible, warnings = _apply_relevance_gate([], settings)
    assert eligible == [] and warnings == []


# ── End-to-end: fewer than 5 qualifying / zero qualifying ───────────────────
@pytest.mark.asyncio
async def test_fewer_than_five_qualifying_returns_fewer_with_warning(db_session):
    ev = [("https://www.instagram.com/creatorx/", "Creator X (@creatorx)", "AI marketing")]
    resp = await _run(
        db_session, ev,
        [_criteria(), {"creators": [_row("creatorx", 60, 0.6)]}],
    )
    assert len(resp.results) == 1
    assert any("met the relevance threshold" in w for w in resp.warnings)


@pytest.mark.asyncio
async def test_zero_qualifying_returns_empty_shortlist(db_session):
    ev = [("https://www.instagram.com/creatorx/", "Creator X (@creatorx)", "AI marketing")]
    resp = await _run(
        db_session, ev,
        [_criteria(), {"creators": [_row("creatorx", 15, 0.9)]}],  # score too low
    )
    assert resp.results == []
    assert any("No creators met the relevance threshold" in w for w in resp.warnings)


@pytest.mark.asyncio
async def test_weak_creators_not_padded_to_minimum(db_session):
    ev = [
        (f"https://www.instagram.com/creator{i}/", f"Creator {i} (@creator{i})", "AI marketing")
        for i in range(3)
    ]
    rows = [_row("creator0", 70, 0.7), _row("creator1", 20, 0.9), _row("creator2", 65, 0.6)]
    resp = await _run(db_session, ev, [_criteria(), {"creators": rows}])
    handles = {r["handle"] for r in [x.model_dump() for x in resp.results]}
    assert handles == {"@creator0", "@creator2"}  # creator1 excluded, not padded in
    scores = [r.score for r in resp.results]
    assert scores == sorted(scores, reverse=True)


# ── Discovery query construction: combined-intent prioritized, cap respected ─
def test_combined_queries_prioritized_over_generic_single_topic():
    criteria = SearchCriteria(
        topics=["AI", "marketing", "entrepreneurship"],
        geo_related_topics=["AI search", "generative engine optimization"],
        search_queries=["AI search marketing creator"],
    )
    queries = _discovery_queries(criteria, cap=6)
    assert len(queries) <= 6
    # First query must combine two concepts (contains a space-separated pair
    # of topic/GEO words), not be a bare single-topic query like "ai instagram creator".
    assert queries[0] != "ai instagram creator"
    assert "marketing" in queries[0] or "ai" in queries[0]
    combined_count = sum(
        1 for q in queries
        if sum(t.lower() in q.lower() for t in ["ai", "marketing", "entrepreneurship",
                                                  "ai search", "generative engine optimization"]) >= 2
    )
    assert combined_count >= 3  # majority of the 6-query budget is combined-intent


def test_discovery_query_count_never_exceeds_cap():
    criteria = SearchCriteria(
        topics=["AI", "marketing", "entrepreneurship", "emerging technology"],
        geo_related_topics=["AI search", "GEO", "future of search"],
        search_queries=[f"query {i}" for i in range(20)],
    )
    for cap in (4, 6, 8):
        assert len(_discovery_queries(criteria, cap=cap)) <= cap


def test_discovery_queries_deduplicated():
    criteria = SearchCriteria(topics=["AI"], geo_related_topics=[], search_queries=["AI instagram creator"])
    queries = _discovery_queries(criteria, cap=6)
    assert len(queries) == len(set(q.lower() for q in queries))
