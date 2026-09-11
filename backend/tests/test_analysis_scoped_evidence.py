"""FIX 1 — evidence shown on a result is scoped to the analysis that produced it,
not every source ever seen for that creator."""
import pytest

from app.config.settings import get_settings
from app.models.db_models import AnalysisEvidence, CreatorAnalysis
from app.services import creator_service, search_orchestrator
from app.services.deduplication import resolve_evidence_indices
from tests.conftest import FakeLLM, FakeProvider

GEO = {
    "summary": "",
    "very_strong_signals": [],
    "related_signals": [],
    "weak_or_generic_signals": [],
    "negative_signals": [],
    "ideal_creator_profiles": [],
}

# Three distinct evidence URLs that all resolve to handle "creatorx".
EV_A = ("https://www.instagram.com/creatorx/", "Creator X (@creatorx) A", "AI marketing evidence A")
EV_B = ("https://instagram.com/creatorx", "Creator X (@creatorx) B", "AI marketing evidence B")
EV_C = ("https://www.instagram.com/creatorx/?hl=en", "Creator X (@creatorx) C", "entrepreneurship evidence C")


def _criteria_response(queries=("q1",)):
    return {
        "topics": ["AI"],
        "geo_related_topics": ["AI search"],
        "creator_types": ["educator"],
        "search_queries": list(queries),
    }


def _analysis_response(handle="creatorx", indices=None, **scores):
    row = {
        "handle": handle,
        "name": "Creator X",
        "relevant_topics": ["AI"],
        "geo_concepts": [],
        "content_summary": "evidence-based",
        "geo_search_relevance": scores.get("geo", 60),
        "topic_relevance": scores.get("topic", 60),
        "content_relevance": scores.get("content", 60),
        "creator_fit": scores.get("fit", 60),
        "fit_explanation": "ok",
        "confidence": 0.7,
        "warnings": [],
    }
    if indices is not None:
        row["evidence_indices"] = indices
    return {"creators": [row]}


async def _run(db, brief, provider_results, llm_responses, limit=8):
    return await search_orchestrator.run_search(
        db,
        brief=brief,
        limit=limit,
        force_refresh=True,
        settings=get_settings(),
        llm=FakeLLM(llm_responses),
        providers=[FakeProvider("tavily", results_by_query={"*": provider_results})],
        geo_playbook=GEO,
    )


# ── Test D + E: index validation ────────────────────────────────────────────
@pytest.mark.parametrize(
    "indices,sent,expected",
    [
        ([0, 2], 3, [0, 2]),
        ([-1, 5, 2], 3, [2]),        # negative + out of range dropped
        ([1, 1, 1], 3, [1]),         # duplicates collapsed
        (["1", 0, "x"], 3, [1, 0]),  # string coercion + garbage dropped
        ([], 3, []),
        ([0, 1], 0, []),             # nothing was sent
    ],
)
def test_resolve_evidence_indices(indices, sent, expected):
    assert resolve_evidence_indices(indices, sent) == expected


# ── Test A: historical evidence is not attached to a later analysis ─────────
@pytest.mark.asyncio
async def test_later_analysis_returns_only_its_own_evidence(db_session):
    # Search 1: creator discovered with evidence A and B.
    await _run(
        db_session,
        "Find AI marketing creators",
        [EV_A, EV_B],
        [_criteria_response(), _analysis_response(indices=[0, 1])],
    )

    # Search 2 (different brief): the same creator, but only evidence C this time.
    resp2 = await _run(
        db_session,
        "Find entrepreneurship creators",
        [EV_C],
        [_criteria_response(("q2",)), _analysis_response(indices=[0])],
    )

    assert resp2.results, "expected creatorx to be returned"
    urls = {e.source_url for e in resp2.results[0].evidence}
    assert urls == {EV_C[0]}
    assert EV_A[0] not in urls and EV_B[0] not in urls

    # Two analyses were stored, and the creator still owns all 3 evidence rows,
    # but each analysis only links to its own.
    assert db_session.query(CreatorAnalysis).count() == 2
    latest = creator_service.latest_analysis_for_creator(db_session, resp2.results[0].id)
    assert {e.source_url for e in latest.creator.evidence} == {EV_A[0], EV_B[0], EV_C[0]}


# ── Test B: cached replay returns the exact evidence of the cached analysis ──
@pytest.mark.asyncio
async def test_cached_replay_returns_snapshot_evidence(db_session):
    settings = get_settings()
    brief = "Find AI marketing creators for GEO"

    # Search 1 stores creatorx with evidence A + B.
    await _run(db_session, brief, [EV_A, EV_B],
               [_criteria_response(), _analysis_response(indices=[0, 1])])

    # A *different* later search discovers evidence C for the same creator,
    # producing a new analysis. This must not alter the first (cached) one.
    await _run(db_session, "another brief entirely", [EV_C],
               [_criteria_response(("q9",)), _analysis_response(indices=[0])])

    # Cached replay of the first brief (no force_refresh).
    cached = await search_orchestrator.run_search(
        db_session, brief=brief, limit=8, force_refresh=False, settings=settings,
        llm=FakeLLM([]), providers=[], geo_playbook=GEO,
    )
    assert cached.data_status == "cached"
    urls = {e.source_url for e in cached.results[0].evidence}
    assert urls == {EV_A[0], EV_B[0]}
    assert EV_C[0] not in urls


# ── Test C: refresh creates a new association, old analysis unchanged ───────
@pytest.mark.asyncio
async def test_refresh_adds_new_association_without_touching_old(db_session):
    settings = get_settings()
    resp1 = await _run(db_session, "Find AI marketing creators", [EV_A, EV_B],
                       [_criteria_response(), _analysis_response(indices=[0, 1])])
    creator_id = resp1.results[0].id
    old_analysis_id = creator_service.latest_analysis_for_creator(db_session, creator_id).id
    old_links_before = {
        l.evidence.source_url
        for l in db_session.get(CreatorAnalysis, old_analysis_id).evidence_links
    }
    assert old_links_before == {EV_A[0], EV_B[0]}

    refreshed = await search_orchestrator.refresh_creator(
        db_session, creator_id=creator_id, settings=settings,
        llm=FakeLLM([_criteria_response(("r1",)), _analysis_response(indices=[0])]),
        providers=[FakeProvider("tavily", results_by_query={"*": [EV_C]})],
        geo_playbook=GEO,
    )
    assert refreshed is not None
    new_urls = {e.source_url for e in refreshed.creator.evidence}
    assert new_urls == {EV_C[0]}

    # old analysis links are exactly as before
    old_links_after = {
        l.evidence.source_url
        for l in db_session.get(CreatorAnalysis, old_analysis_id).evidence_links
    }
    assert old_links_after == old_links_before


# ── Refresh when re-discovery misses the handle: reuse stored evidence ─────
@pytest.mark.asyncio
async def test_refresh_reuses_stored_evidence_when_rediscovery_misses(db_session):
    settings = get_settings()
    resp1 = await _run(db_session, "Find AI marketing creators", [EV_A, EV_B],
                       [_criteria_response(), _analysis_response(indices=[0, 1])])
    creator_id = resp1.results[0].id

    # Refresh, but the provider returns an unrelated profile (not creatorx).
    refreshed = await search_orchestrator.refresh_creator(
        db_session, creator_id=creator_id, settings=settings,
        llm=FakeLLM([
            _criteria_response(("r1",)),
            _analysis_response(indices=[0, 1], geo=70, topic=70, content=70, fit=70),
        ]),
        providers=[FakeProvider("tavily", results_by_query={"*": [
            ("https://www.instagram.com/someoneelse/", "Someone Else (@someoneelse)", "unrelated"),
        ]})],
        geo_playbook=GEO,
    )
    assert refreshed is not None
    urls = {e.source_url for e in refreshed.creator.evidence}
    assert urls == {EV_A[0], EV_B[0]}          # re-analyzed against known evidence
    assert refreshed.creator.score > 0          # not tanked to ~0 for lack of evidence


# ── Fallback: no valid indices -> attach all evidence sent to that analysis ──
@pytest.mark.asyncio
async def test_no_valid_indices_falls_back_to_supplied_evidence_only(db_session):
    resp = await _run(
        db_session, "Find AI marketing creators", [EV_A, EV_B],
        [_criteria_response(), _analysis_response(indices=[99, -3])],  # all invalid
    )
    urls = {e.source_url for e in resp.results[0].evidence}
    assert urls == {EV_A[0], EV_B[0]}  # both supplied items, nothing historical/unrelated


# ── Test E (API level): duplicate indices do not duplicate evidence ────────
@pytest.mark.asyncio
async def test_duplicate_indices_do_not_duplicate_api_evidence(db_session):
    resp = await _run(
        db_session, "Find AI marketing creators", [EV_A, EV_B],
        [_criteria_response(), _analysis_response(indices=[0, 0, 0, 1, 1])],
    )
    ev = resp.results[0].evidence
    assert len(ev) == len({e.source_url for e in ev}) == 2
