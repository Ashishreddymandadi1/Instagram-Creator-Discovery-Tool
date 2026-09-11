"""Deterministic, explainable relevance scoring.

The overall score is ALWAYS computed here from four component signals using
fixed weights. The LLM classifies the components against a documented rubric
(see docs/scoring.md); it never returns the overall number.

    overall = geo*0.35 + topic*0.30 + content*0.25 + fit*0.10
"""
from __future__ import annotations

from dataclasses import dataclass

# Fixed rubric weights — must sum to 1.0. Do not change without updating docs.
WEIGHT_GEO_SEARCH = 0.35
WEIGHT_TOPIC = 0.30
WEIGHT_CONTENT = 0.25
WEIGHT_CREATOR_FIT = 0.10

_MIN = 0.0
_MAX = 100.0


def clamp(value: float) -> float:
    """Clamp a component score to 0–100. Non-numeric -> 0."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _MIN
    if v != v:  # NaN
        return _MIN
    return max(_MIN, min(_MAX, v))


@dataclass(frozen=True, slots=True)
class ScoreComponents:
    geo_search_relevance: float
    topic_relevance: float
    content_relevance: float
    creator_fit: float

    def clamped(self) -> "ScoreComponents":
        return ScoreComponents(
            clamp(self.geo_search_relevance),
            clamp(self.topic_relevance),
            clamp(self.content_relevance),
            clamp(self.creator_fit),
        )


def calculate_relevance_score(
    geo_search_relevance: float,
    topic_relevance: float,
    content_relevance: float,
    creator_fit: float,
) -> int:
    """Return the final 0–100 integer relevance score."""
    geo = clamp(geo_search_relevance)
    topic = clamp(topic_relevance)
    content = clamp(content_relevance)
    fit = clamp(creator_fit)

    raw = (
        geo * WEIGHT_GEO_SEARCH
        + topic * WEIGHT_TOPIC
        + content * WEIGHT_CONTENT
        + fit * WEIGHT_CREATOR_FIT
    )
    return int(round(min(_MAX, max(_MIN, raw))))


def score_from_components(components: ScoreComponents) -> int:
    c = components.clamped()
    return calculate_relevance_score(
        c.geo_search_relevance, c.topic_relevance, c.content_relevance, c.creator_fit
    )
