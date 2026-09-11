"""Environment-driven configuration (Pydantic Settings).

All secrets come from the environment / backend/.env. Nothing here is ever
returned to the frontend as a value — only booleans via /api/health.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── LLM provider ────────────────────────────────────────
    # Env var names kept as ANTHROPIC_* since that is the underlying SDK in
    # use; everything user/API-facing describes this neutrally as "the LLM".
    anthropic_api_key: str = ""
    # Fast/cheap default for high-volume structured classification. Bump to
    # a stronger model for deeper reasoning on nuanced GEO-fit judgements.
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_timeout_seconds: float = 40.0

    # ─── Search providers ────────────────────────────────────
    tavily_api_key: str = ""
    serper_api_key: str = ""
    brave_api_key: str = ""
    # Currently serving via Serper. Tavily is temporarily paused (its provider
    # implementation and tests are fully retained — switch back any time by
    # setting this to "tavily", no code changes required). Brave / keyless
    # remain optional — opt in by listing them here.
    search_providers: str = "serper"

    # ─── Discovery / ranking ─────────────────────────────────
    max_search_queries: int = 6
    # Upper bound on valid Instagram candidates collected from search (this is
    # what the API reports as `candidate_count`).
    max_candidates: int = 24
    # Maximum number of discovered candidates sent to the LLM for semantic
    # analysis/scoring. Kept modest so one batched analysis call stays a
    # reasonable size/cost. Discovery order front-loads the strongest queries,
    # so the first `max_analysis_candidates` are analyzed.
    max_analysis_candidates: int = 14
    default_result_limit: int = 8
    min_result_limit: int = 5
    max_result_limit: int = 10
    # Credibility gate: a creator must clear BOTH thresholds to make the
    # shortlist. This does not touch the 35/30/25/10 weighting formula — it
    # filters *after* the deterministic score is computed. Weak matches are
    # excluded outright rather than padding the shortlist up to min_result_limit.
    min_relevance_score: int = 40
    min_result_confidence: float = 0.35

    # ─── Cache ───────────────────────────────────────────────
    cache_ttl_hours: float = 24.0

    # ─── HTTP / server ───────────────────────────────────────
    http_timeout_seconds: float = 12.0
    database_url: str = "sqlite:///./data/geo_creator_scout.db"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    @field_validator("search_providers", "cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    # ─── Derived helpers ─────────────────────────────────────
    @property
    def llm_configured(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def llm_model(self) -> str:
        return self.anthropic_model

    @property
    def provider_priority(self) -> list[str]:
        return [p.strip().lower() for p in self.search_providers.split(",") if p.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def configured_key_providers(self) -> list[str]:
        """Keyed providers (in priority order) that actually have a key set."""
        keys = {
            "tavily": self.tavily_api_key,
            "serper": self.serper_api_key,
            "brave": self.brave_api_key,
        }
        return [p for p in self.provider_priority if p in keys and keys[p].strip()]

    def active_providers(self) -> list[str]:
        """All providers that will run: keyed-with-key + 'keyless' if listed."""
        active = self.configured_key_providers()
        if "keyless" in self.provider_priority:
            active.append("keyless")
        return active


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_geo_playbook() -> dict:
    """The editable GEO domain model. Replace geo_playbook.json with the real
    GEO Playbook later without touching code."""
    path = CONFIG_DIR / "geo_playbook.json"
    return json.loads(path.read_text(encoding="utf-8"))
