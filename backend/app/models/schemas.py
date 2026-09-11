"""Pydantic schemas — the API contract and all validated LLM I/O.

Data-quality rule: unavailable values are None / "Not available". Nothing here
generates follower counts, engagement, verification, bios, or locations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DataStatus = Literal["live", "cached", "partial", "demo"]


# ─────────────────────────────────────────────────────────────
# Evidence & provenance
# ─────────────────────────────────────────────────────────────
class Evidence(BaseModel):
    source_provider: str
    source_url: str
    title: str | None = None
    snippet: str | None = None
    retrieved_at: datetime
    synthetic: bool = False  # True only for clearly-labelled dev fixtures


# ─────────────────────────────────────────────────────────────
# Query understanding (LLM output, validated)
# ─────────────────────────────────────────────────────────────
class SearchCriteria(BaseModel):
    topics: list[str] = Field(default_factory=list)
    geo_related_topics: list[str] = Field(default_factory=list)
    creator_types: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)

    @field_validator("topics", "geo_related_topics", "creator_types", "search_queries")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            s = (item or "").strip()
            key = s.lower()
            if s and key not in seen:
                seen.add(key)
                out.append(s)
        return out


# ─────────────────────────────────────────────────────────────
# Creator analysis (LLM output, validated)
# ─────────────────────────────────────────────────────────────
def _clamp_score(v: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, f))


class LLMCreatorAnalysis(BaseModel):
    """What the LLM returns per candidate. The model supplies component signals
    only — it never returns the overall score."""

    name: str | None = None
    handle: str
    relevant_topics: list[str] = Field(default_factory=list)
    geo_concepts: list[str] = Field(default_factory=list)
    content_summary: str = "Not available"
    geo_search_relevance: float = 0.0
    topic_relevance: float = 0.0
    content_relevance: float = 0.0
    creator_fit: float = 0.0
    fit_explanation: str = "Not available"
    evidence_indices: list[int] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)

    @field_validator(
        "geo_search_relevance", "topic_relevance", "content_relevance", "creator_fit",
        mode="before",
    )
    @classmethod
    def _scores(cls, v: float) -> float:
        return _clamp_score(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: float) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("handle")
    @classmethod
    def _handle(cls, v: str) -> str:
        s = (v or "").strip().lstrip("@").lower()
        if not s:
            raise ValueError("handle is required")
        return s

    @field_validator("content_summary", "fit_explanation", mode="before")
    @classmethod
    def _text_default(cls, v: object) -> str:
        s = str(v).strip() if v is not None else ""
        return s or "Not available"

    @field_validator("name", mode="before")
    @classmethod
    def _name_blank_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


# ─────────────────────────────────────────────────────────────
# API response models
# ─────────────────────────────────────────────────────────────
class ScoreBreakdown(BaseModel):
    geo_search_relevance: int
    topic_relevance: int
    content_relevance: int
    creator_fit: int


class CreatorResult(BaseModel):
    id: int
    name: str | None
    handle: str                       # "@handle"
    instagram_url: str
    relevant_topics: list[str]
    geo_concepts: list[str] = Field(default_factory=list)
    content_summary: str
    bio_or_summary: str | None = None
    score: int
    score_breakdown: ScoreBreakdown
    explanation: str
    confidence: float
    data_status: DataStatus
    last_updated: datetime
    evidence: list[Evidence]
    warnings: list[str] = Field(default_factory=list)

    # Explicitly-unavailable fields (never fabricated)
    follower_count: int | None = None
    engagement_rate: float | None = None
    verified: bool | None = None
    location: str | None = None


class SearchRequest(BaseModel):
    brief: str = Field(min_length=3, max_length=600)
    limit: int | None = None
    force_refresh: bool = False


class SearchResponse(BaseModel):
    brief: str
    criteria: SearchCriteria
    results: list[CreatorResult]
    # Number of valid, deduplicated Instagram creator candidates *discovered* via
    # search. NOT the number analyzed by the LLM — only a bounded subset
    # (settings.max_analysis_candidates) of these is sent for semantic
    # analysis/scoring; `returned_count` is how many made the final shortlist.
    candidate_count: int
    returned_count: int
    data_status: DataStatus
    warnings: list[str] = Field(default_factory=list)


class RefreshResponse(BaseModel):
    creator: CreatorResult
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    llm_configured: bool
    llm_model: str
    search_providers: list[str]
    cache_ttl_hours: float
