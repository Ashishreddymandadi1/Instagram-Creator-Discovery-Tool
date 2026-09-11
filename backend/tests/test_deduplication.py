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


def test_reel_with_explicit_handle_is_recovered_as_profile():
    results = [
        _r(
            "https://www.instagram.com/reel/Dxyz123/",
            title="Recovered Creator (@recoveredcreator) on Instagram",
            snippet="AI search marketing reel",
        ),
    ]
    candidates = build_candidates(results)
    assert len(candidates) == 1
    assert candidates[0].handle == "recoveredcreator"
    # The reel URL itself is never returned as the profile URL.
    assert candidates[0].instagram_url == "https://www.instagram.com/recoveredcreator/"
    # Original reel URL/title/snippet preserved as evidence.
    assert candidates[0].evidence[0].url == "https://www.instagram.com/reel/Dxyz123/"


def test_post_without_explicit_handle_is_not_recovered():
    results = [
        _r(
            "https://www.instagram.com/p/Dabc123/",
            title="A great post about AI marketing",
            snippet="no handle mentioned here",
        ),
    ]
    assert build_candidates(results) == []


def test_handle_recovery_never_applies_to_non_instagram_source():
    results = [
        _r(
            "https://example.com/blog/post",
            title="Shoutout to @realhandle on Instagram",
            snippet="great creator",
        ),
    ]
    assert build_candidates(results) == []


def test_recovered_handle_dedupes_with_direct_profile():
    results = [
        _r("https://www.instagram.com/dualcreator/", title="direct profile"),
        _r(
            "https://www.instagram.com/reel/Dxyz999/",
            title="Dual Creator (@dualcreator) on Instagram",
            snippet="AI search reel",
        ),
    ]
    candidates = build_candidates(results)
    assert len(candidates) == 1
    assert candidates[0].handle == "dualcreator"
    assert len(candidates[0].evidence) == 2
