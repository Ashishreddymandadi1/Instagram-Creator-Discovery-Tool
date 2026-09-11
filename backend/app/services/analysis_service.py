"""Batched LLM creator analysis -> validated LLMCreatorAnalysis per candidate."""
from __future__ import annotations

import logging

from app.models.schemas import LLMCreatorAnalysis, SearchCriteria
from app.services.llm_service import LLMService, LLMUnavailableError
from app.services.deduplication import (
    MAX_EVIDENCE_PER_ANALYSIS,
    Candidate,
    resolve_evidence_indices,
)
from app.services.prompts import build_creator_analysis_messages

logger = logging.getLogger(__name__)

_MAX_SNIPPET = 500
_MAX_EVIDENCE_PER_CANDIDATE = MAX_EVIDENCE_PER_ANALYSIS

__all__ = ["analyze_candidates", "AnalysisOutcome", "resolve_evidence_indices"]


class AnalysisOutcome:
    __slots__ = ("analyses", "warnings", "failed")

    def __init__(
        self,
        analyses: dict[str, LLMCreatorAnalysis],
        warnings: list[str],
        failed: bool,
    ):
        self.analyses = analyses          # handle -> analysis
        self.warnings = warnings
        self.failed = failed


def _candidate_payload(candidates: list[Candidate]) -> list[dict]:
    payload: list[dict] = []
    for cand in candidates:
        evidence = []
        for ev in cand.evidence[:_MAX_EVIDENCE_PER_CANDIDATE]:
            evidence.append(
                {
                    "index": len(evidence),
                    "provider": ev.provider,
                    "title": (ev.title or "")[:_MAX_SNIPPET],
                    "snippet": (ev.snippet or "")[:_MAX_SNIPPET],
                    "url": ev.url,
                }
            )
        payload.append(
            {
                "handle": cand.handle,
                "instagram_url": cand.instagram_url,
                "display_name_hint": cand.display_name,
                "evidence": evidence,
            }
        )
    return payload


async def analyze_candidates(
    brief: str,
    criteria: SearchCriteria,
    geo_playbook: dict,
    candidates: list[Candidate],
    llm: LLMService,
) -> AnalysisOutcome:
    if not candidates:
        return AnalysisOutcome({}, [], failed=False)

    messages = build_creator_analysis_messages(
        brief, criteria, geo_playbook, _candidate_payload(candidates)
    )
    try:
        raw = await llm.complete_json(messages, max_tokens=6000)
    except LLMUnavailableError as exc:
        logger.warning("Creator analysis failed: %s", exc)
        return AnalysisOutcome(
            {},
            ["AI creator analysis was unavailable, so no creators could be scored."],
            failed=True,
        )

    rows = raw.get("creators")
    if not isinstance(rows, list):
        return AnalysisOutcome(
            {}, ["AI creator analysis returned an unexpected shape."], failed=True
        )

    valid_handles = {c.handle for c in candidates}
    analyses: dict[str, LLMCreatorAnalysis] = {}
    warnings: list[str] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            analysis = LLMCreatorAnalysis.model_validate(row)
        except Exception as exc:  # one bad row must not sink the batch
            logger.info("Dropped malformed analysis row: %s", exc)
            continue
        if analysis.handle not in valid_handles:
            continue
        analyses.setdefault(analysis.handle, analysis)

    missing = valid_handles - analyses.keys()
    if missing:
        warnings.append(
            f"{len(missing)} candidate(s) could not be analyzed and were dropped."
        )
    return AnalysisOutcome(analyses, warnings, failed=not analyses)
