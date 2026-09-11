"""LLM prompt construction. Kept out of route handlers on purpose.

Golden rule embedded in every system prompt: use ONLY supplied evidence, never
invent facts (jobs, followers, locations, companies, post titles, bios).
"""
from __future__ import annotations

import json
from typing import Any

from app.models.schemas import SearchCriteria

_NO_INVENT = (
    "CRITICAL RULES:\n"
    "- Use ONLY the evidence text provided. Do NOT use outside knowledge.\n"
    "- NEVER invent follower counts, engagement rates, verification status, "
    "locations, employers, awards, biographies, or specific post titles.\n"
    "- If the evidence is thin, lower `confidence` and the component scores and "
    "add a short note to `warnings`.\n"
    "- Return ONLY valid minified JSON. No markdown, no commentary."
)


def _geo_block(geo_playbook: dict[str, Any]) -> str:
    keep = {
        k: geo_playbook.get(k)
        for k in (
            "summary",
            "very_strong_signals",
            "related_signals",
            "weak_or_generic_signals",
            "negative_signals",
            "ideal_creator_profiles",
        )
    }
    return json.dumps(keep, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────
# 1. Brief understanding
# ─────────────────────────────────────────────────────────────
def build_brief_parse_messages(brief: str, geo_playbook: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You convert a recruiter-style brief into structured Instagram creator "
        "search criteria for a GEO (Generative Engine Optimization) outreach tool.\n\n"
        f"GEO CONTEXT:\n{_geo_block(geo_playbook)}\n\n"
        "Return JSON with EXACTLY these keys:\n"
        '{"topics": [string], "geo_related_topics": [string], '
        '"creator_types": [string], "search_queries": [string]}\n\n'
        "- topics: 3-6 concrete subject areas explicitly implied by the brief.\n"
        "- geo_related_topics: 3-6 GEO/AI-search themes to look for (draw on GEO CONTEXT).\n"
        "- creator_types: 3-5 kinds of creators/personas that fit.\n"
        "- search_queries: 4-8 short natural keyword queries (3-6 words each) for "
        "finding Instagram creator profiles. Do NOT use search operators like "
        "site: or boolean OR. Do NOT wrap phrases in quotes. Each query mixes one "
        "brief topic with a GEO/AI-search angle and a creator word, e.g. "
        "'AI search marketing creator', 'generative engine optimization educator', "
        "'AI Overviews SEO instagram creator'. Keep them varied, no near-duplicates.\n\n"
        + _NO_INVENT
    )
    user = f'BRIEF:\n"""{brief.strip()}"""'
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ─────────────────────────────────────────────────────────────
# 2. Batched creator analysis
# ─────────────────────────────────────────────────────────────
def build_creator_analysis_messages(
    brief: str,
    criteria: SearchCriteria,
    geo_playbook: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """`candidates`: [{"handle": str, "instagram_url": str,
    "evidence": [{"index": int, "provider": str, "title": str, "snippet": str,
    "url": str}]}]"""
    system = (
        "You evaluate Instagram creators for relevance to a GEO Playbook "
        "(Generative Engine Optimization: optimizing for AI-driven search / "
        "answer engines like ChatGPT Search, Perplexity, Google AI Overviews).\n\n"
        f"GEO CONTEXT:\n{_geo_block(geo_playbook)}\n\n"
        "SCORING RUBRIC — score each 0-100 from the evidence only:\n"
        "1. geo_search_relevance (35% weight): how strongly evidence ties the "
        "creator to GEO / AI-search / future-of-search / SEO-for-AI themes. "
        "Very strong signals score 80-100; only generic 'AI' mentions score 20-45; "
        "no signal scores 0-15.\n"
        "2. topic_relevance (30%): overlap between the creator's evidence and the "
        "brief topics: " + json.dumps(criteria.topics, ensure_ascii=False) + ".\n"
        "3. content_relevance (25%): does evidence show the creator actually "
        "MAKES content on these subjects (talks/teaches/analyses), vs. a bare "
        "one-word bio label? Demonstrated content 70-100; vague label 20-40.\n"
        "4. creator_fit (10%): do they look like an educator / analyst / founder / "
        "thought leader who would share professional material? Do NOT use follower "
        "count. Do NOT penalize missing follower data.\n\n"
        "Return JSON: {\"creators\": [ {\n"
        '  "handle": "<lowercase handle without @>",\n'
        '  "name": <string or null - only if a real display name appears in evidence>,\n'
        '  "relevant_topics": [string], "geo_concepts": [string],\n'
        '  "content_summary": "<=350 chars, evidence-grounded, or \\"Not available\\"",\n'
        '  "geo_search_relevance": 0-100, "topic_relevance": 0-100,\n'
        '  "content_relevance": 0-100, "creator_fit": 0-100,\n'
        '  "fit_explanation": "1-3 sentences citing what the evidence shows",\n'
        '  "evidence_indices": [int],  "confidence": 0.0-1.0, "warnings": [string]\n'
        "} ] }\n"
        "Include EVERY candidate exactly once, same handle you were given. "
        "Do NOT output an overall score — the backend computes it.\n\n"
        + _NO_INVENT
    )
    user = json.dumps(
        {
            "brief": brief.strip(),
            "brief_topics": criteria.topics,
            "geo_related_topics": criteria.geo_related_topics,
            "candidates": candidates,
        },
        ensure_ascii=False,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
