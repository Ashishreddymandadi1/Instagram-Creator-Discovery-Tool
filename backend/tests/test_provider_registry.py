"""Provider registry: Serper-only by default (currently serving); Tavily is
paused but its implementation is fully retained and works when opted back in;
others are opt-in; keys never exposed.

Every key field is set explicitly in every case (even to "") so these tests
stay deterministic regardless of what real keys happen to be in a developer's
local backend/.env — Settings.env_file would otherwise leak them in.
"""
from app.config.settings import Settings
from app.providers.registry import build_providers


def test_default_is_serper_only():
    s = Settings(
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="k2", brave_api_key="k3"
    )
    names = [p.name for p in build_providers(s)]
    assert names == ["serper"]


def test_tavily_still_works_when_opted_back_in():
    """Tavily's provider code is retained — switching back needs no code change."""
    s = Settings(
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="", brave_api_key="",
        search_providers="tavily",
    )
    assert [p.name for p in build_providers(s)] == ["tavily"]


def test_opt_in_additional_providers():
    s = Settings(
        anthropic_api_key="x", tavily_api_key="k1", serper_api_key="k2", brave_api_key="",
        search_providers="serper,tavily",
    )
    assert [p.name for p in build_providers(s)] == ["serper", "tavily"]


def test_provider_listed_but_no_key_is_skipped():
    s = Settings(
        anthropic_api_key="x", tavily_api_key="", serper_api_key="k2", brave_api_key="",
        search_providers="serper,tavily,brave",
    )
    assert [p.name for p in build_providers(s)] == ["serper"]


def test_keyless_is_opt_in_only():
    default = Settings(
        anthropic_api_key="x", tavily_api_key="", serper_api_key="k2", brave_api_key=""
    )
    assert "keyless" not in [p.name for p in build_providers(default)]
    opted = Settings(
        anthropic_api_key="x", tavily_api_key="", serper_api_key="k2", brave_api_key="",
        search_providers="serper,keyless",
    )
    assert [p.name for p in build_providers(opted)] == ["serper", "keyless"]


def test_active_providers_never_contains_key_values():
    s = Settings(
        anthropic_api_key="secret-llm", tavily_api_key="", serper_api_key="secret-serper",
        brave_api_key="",
    )
    assert s.active_providers() == ["serper"]
    assert "secret-serper" not in str(s.active_providers())
