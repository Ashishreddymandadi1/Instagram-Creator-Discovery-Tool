"""HTTP providers: parsing + graceful failure. Network mocked with respx."""
import json

import httpx
import pytest
import respx

from app.providers.brave import BraveSearchProvider
from app.providers.optional_no_key_provider import OptionalNoKeyProvider
from app.providers.serper import SerperSearchProvider
from app.providers.tavily import TavilySearchProvider


@pytest.mark.asyncio
@respx.mock
async def test_tavily_parses_results_and_scopes_domain():
    route = respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(200, json={"results": [
            {"url": "https://www.instagram.com/foo/", "title": "Foo (@foo)", "content": "AI search"},
            {"title": "no url"},
        ]})
    )
    p = TavilySearchProvider("key", timeout=5)
    out = await p.search("AI creator", limit=10)
    assert [r.url for r in out] == ["https://www.instagram.com/foo/"]
    assert route.calls.last.request.content
    assert b"instagram.com" in route.calls.last.request.content


@pytest.mark.asyncio
@respx.mock
async def test_tavily_http_error_returns_empty():
    respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(429, text="rate"))
    p = TavilySearchProvider("key", timeout=5)
    assert await p.search("q") == []


@pytest.mark.asyncio
async def test_tavily_no_key_returns_empty():
    assert await TavilySearchProvider("", timeout=5).search("q") == []


@pytest.mark.asyncio
@respx.mock
async def test_serper_sends_plain_query_and_parses():
    # Free-tier Serper rejects `site:` (and quoted) query patterns outright, so
    # the provider must send a plain query and never add site:instagram.com.
    route = respx.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(200, json={"organic": [
            {"link": "https://www.instagram.com/bar/", "title": "Bar", "snippet": "GEO"},
        ]})
    )
    out = await SerperSearchProvider("key", timeout=5).search('site:instagram.com "marketing" creator')
    assert out[0].url == "https://www.instagram.com/bar/"
    sent_q = json.loads(route.calls.last.request.content)["q"]
    assert "site:" not in sent_q
    assert '"' not in sent_q
    assert "marketing creator" in sent_q


@pytest.mark.asyncio
@respx.mock
async def test_brave_parses_and_handles_500():
    respx.get("https://api.search.brave.com/res/v1/web/search").mock(
        return_value=httpx.Response(500, text="err")
    )
    assert await BraveSearchProvider("key", timeout=5).search("q") == []


@pytest.mark.asyncio
@respx.mock
async def test_keyless_filters_to_instagram():
    html = '''
    <a class="result__a" href="https://www.instagram.com/keylesscreator/">Keyless Creator</a>
    <a class="result__snippet" href="#">AI search snippet</a>
    <a class="result__a" href="https://example.com/other">Not IG</a>
    '''
    respx.get("https://html.duckduckgo.com/html/").mock(return_value=httpx.Response(200, text=html))
    out = await OptionalNoKeyProvider(timeout=5).search("q", limit=10)
    assert all("instagram.com" in r.url for r in out)
    assert out and out[0].url == "https://www.instagram.com/keylesscreator/"
