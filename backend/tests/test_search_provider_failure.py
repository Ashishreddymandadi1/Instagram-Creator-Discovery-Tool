"""One search provider failing must not kill discovery when another works."""
import pytest

from app.services.discovery_service import discover_candidates
from tests.conftest import FakeProvider

GOOD = {
    "*": [
        ("https://www.instagram.com/goodcreator/", "Good Creator (@goodcreator) • Instagram", "AI search"),
        ("https://www.instagram.com/p/Dxyz/", "a post", "ignored"),
    ]
}


@pytest.mark.asyncio
async def test_failing_provider_does_not_break_search():
    bad = FakeProvider("brave", raises=True)
    good = FakeProvider("tavily", results_by_query=GOOD)
    outcome = await discover_candidates([bad, good], ["AI creator"], max_candidates=20)
    assert [c.handle for c in outcome.candidates] == ["goodcreator"]
    assert any("brave" in e for e in outcome.provider_errors)


@pytest.mark.asyncio
async def test_all_providers_failing_returns_empty_with_errors():
    a = FakeProvider("tavily", raises=True)
    b = FakeProvider("serper", raises=True)
    outcome = await discover_candidates([a, b], ["AI creator"], max_candidates=20)
    assert outcome.candidates == []
    assert len(outcome.provider_errors) == 2


@pytest.mark.asyncio
async def test_no_providers_configured():
    outcome = await discover_candidates([], ["AI creator"], max_candidates=20)
    assert outcome.candidates == []
    assert outcome.provider_errors
