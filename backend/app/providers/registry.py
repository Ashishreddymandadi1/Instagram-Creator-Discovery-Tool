"""Builds the active provider list from settings, in priority order."""
from __future__ import annotations

import logging

from app.config.settings import Settings
from app.providers.base import SearchProvider
from app.providers.brave import BraveSearchProvider
from app.providers.optional_no_key_provider import OptionalNoKeyProvider
from app.providers.serper import SerperSearchProvider
from app.providers.tavily import TavilySearchProvider

logger = logging.getLogger(__name__)


def build_providers(settings: Settings) -> list[SearchProvider]:
    timeout = settings.http_timeout_seconds
    available: dict[str, SearchProvider] = {
        "tavily": TavilySearchProvider(settings.tavily_api_key, timeout),
        "serper": SerperSearchProvider(settings.serper_api_key, timeout),
        "brave": BraveSearchProvider(settings.brave_api_key, timeout),
        "keyless": OptionalNoKeyProvider(timeout),
    }
    active: list[SearchProvider] = []
    for name in settings.provider_priority:
        provider = available.get(name)
        if provider is None:
            logger.warning("Unknown provider in SEARCH_PROVIDERS: %s", name)
            continue
        if provider.is_configured:
            active.append(provider)
        else:
            logger.info("Provider %s skipped (no API key)", name)
    if not active:
        logger.warning("No search providers configured — discovery will be empty")
    return active
