"""Shared FastAPI dependencies: settings, LLM service, provider list, geo playbook."""
from __future__ import annotations

from functools import lru_cache

from app.config.settings import Settings, get_geo_playbook, get_settings
from app.providers.base import SearchProvider
from app.providers.registry import build_providers
from app.services.llm_service import LLMService


@lru_cache
def _llm_singleton() -> LLMService:
    return LLMService(get_settings())


@lru_cache
def _providers_singleton_key() -> str:
    return get_settings().search_providers


def get_app_settings() -> Settings:
    return get_settings()


def get_llm_service() -> LLMService:
    return _llm_singleton()


def get_search_providers() -> list[SearchProvider]:
    return build_providers(get_settings())


def get_geo_context() -> dict:
    return get_geo_playbook()
