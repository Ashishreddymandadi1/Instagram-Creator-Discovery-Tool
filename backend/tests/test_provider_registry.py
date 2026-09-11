"""Provider registry: Tavily-only by default (active); Serper's implementation
and tests are fully retained and works when opted back in; others are opt-in;
keys never exposed.

Every key field is set explicitly in every case (even to ""), and `_env_file`
is disabled, so these tests stay deterministic regardless of what real keys
or SEARCH_PROVIDERS value happen to be in a developer's local backend/.env.
"""
from app.config.settings import Settings
from app.providers.registry import build_providers


def test_default_is_tavily_only():
    s = Settings(
        _env_file=None,
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="k2", brave_api_key="k3",
    )
    assert s.search_providers == "tavily"
    names = [p.name for p in build_providers(s)]
    assert names == ["tavily"]


def test_tavily_key_and_default_search_providers_activates_tavily_only():
    """Both keys present, SEARCH_PROVIDERS left at its tavily default: Serper
    must not run even though it has a valid key configured."""
    s = Settings(
        _env_file=None,
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="k2", brave_api_key="",
    )
    assert [p.name for p in build_providers(s)] == ["tavily"]
    assert "serper" not in s.active_providers()


def test_serper_still_works_when_opted_back_in():
    """Serper's provider code is retained — switching to it needs no code change."""
    s = Settings(
        _env_file=None,
        anthropic_api_key="x", tavily_api_key="", serper_api_key="k2", brave_api_key="",
        search_providers="serper",
    )
    assert [p.name for p in build_providers(s)] == ["serper"]


def test_opt_in_additional_providers():
    s = Settings(
        _env_file=None,
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="k2", brave_api_key="",
        search_providers="tavily,serper",
    )
    assert [p.name for p in build_providers(s)] == ["tavily", "serper"]


def test_provider_listed_but_no_key_is_skipped():
    s = Settings(
        _env_file=None,
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="", brave_api_key="",
        search_providers="tavily,serper,brave",
    )
    assert [p.name for p in build_providers(s)] == ["tavily"]


def test_keyless_is_opt_in_only():
    default = Settings(
        _env_file=None,
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="", brave_api_key="",
    )
    assert "keyless" not in [p.name for p in build_providers(default)]
    opted = Settings(
        _env_file=None,
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="", brave_api_key="",
        search_providers="tavily,keyless",
    )
    assert [p.name for p in build_providers(opted)] == ["tavily", "keyless"]


def test_active_providers_never_contains_key_values():
    s = Settings(
        _env_file=None,
        anthropic_api_key="secret-llm", tavily_api_key="secret-tavily", serper_api_key="",
        brave_api_key="",
    )
    assert s.active_providers() == ["tavily"]
    assert "secret-tavily" not in str(s.active_providers())
