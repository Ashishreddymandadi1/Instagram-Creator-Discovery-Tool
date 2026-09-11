"""SYNTHETIC DEMO DATA — for automated tests / frontend development ONLY.

These creators are invented. They must NEVER be returned by the live API as
real discovered recommendations. Every evidence item is marked synthetic=True.
"""
from __future__ import annotations

from datetime import datetime, timezone

SYNTHETIC_DEMO_DATA = True

_NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)

SYNTHETIC_CREATORS = [
    {
        "handle": "syntheticgeoeducator",
        "instagram_url": "https://www.instagram.com/syntheticgeoeducator/",
        "display_name": "SYNTHETIC — GEO Educator",
        "evidence": [
            {
                "provider": "synthetic",
                "url": "https://www.instagram.com/syntheticgeoeducator/",
                "title": "SYNTHETIC — GEO Educator (@syntheticgeoeducator) • Instagram",
                "snippet": "SYNTHETIC DEMO DATA — teaches Generative Engine Optimization, "
                "AI Overviews and Perplexity ranking. Not a real account.",
                "retrieved_at": _NOW,
                "synthetic": True,
            }
        ],
        "analysis": {
            "handle": "syntheticgeoeducator",
            "name": "SYNTHETIC — GEO Educator",
            "relevant_topics": ["GEO", "AI search", "SEO"],
            "geo_concepts": ["Generative Engine Optimization", "Google AI Overviews"],
            "content_summary": "SYNTHETIC DEMO DATA.",
            "geo_search_relevance": 95,
            "topic_relevance": 90,
            "content_relevance": 84,
            "creator_fit": 88,
            "fit_explanation": "SYNTHETIC DEMO DATA — do not present as a real recommendation.",
            "evidence_indices": [0],
            "confidence": 0.9,
            "warnings": ["SYNTHETIC DEMO DATA"],
        },
    }
]
