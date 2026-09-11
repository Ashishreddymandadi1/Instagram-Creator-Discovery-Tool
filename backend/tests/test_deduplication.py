"""Candidate dedupe by normalized lowercase handle."""
from datetime import datetime, timezone

from app.providers.base import SearchResult
from app.services.deduplication import build_candidates, merge_candidate_lists


def _r(url, provider="tavily", title=None, snippet=None):
    return SearchResult(provider=provider, url=url, title=title, snippet=snippet,
                        retrieved_at=datetime.now(timezone.utc))


def test_case_and_trailing_slash_collapse_to_one():
    results = [
        _r("https://instagram.com/TestCreator", title="a"),
        _r("https://www.instagram.com/testcreator/", title="b"),
        _r("http://instagram.com/testcreator", title="c"),
    ]
    candidates = build_candidates(results)
    assert len(candidates) == 1
    assert candidates[0].handle == "testcreator"
    assert candidates[0].instagram_url == "https://www.instagram.com/testcreator/"
    assert len(candidates[0].evidence) == 3


def test_post_urls_filtered_out_of_candidates():
    results = [
        _r("https://www.instagram.com/p/Dabc123/"),
        _r("https://www.instagram.com/realhandle/"),
    ]
    candidates = build_candidates(results)
    assert [c.handle for c in candidates] == ["realhandle"]


def test_merge_lists_dedupes_and_unions_evidence():
    a = build_candidates([_r("https://instagram.com/foo", title="x")])
    b = build_candidates([_r("https://instagram.com/FOO/", provider="serper", title="y"),
                          _r("https://instagram.com/bar")])
    merged = merge_candidate_lists(a, b)
    handles = sorted(c.handle for c in merged)
    assert handles == ["bar", "foo"]
    foo = next(c for c in merged if c.handle == "foo")
    assert len(foo.evidence) == 2
