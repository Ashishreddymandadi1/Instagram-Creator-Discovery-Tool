"""POST /api/search — brief -> shortlist of Instagram creators."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.database import get_db
from app.dependencies import (
    get_llm_service,
    get_app_settings,
    get_geo_context,
    get_search_providers,
)
from app.models.schemas import SearchRequest, SearchResponse
from app.providers.base import SearchProvider
from app.services.llm_service import LLMService
from app.services.search_orchestrator import run_search

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    llm: LLMService = Depends(get_llm_service),
    providers: list[SearchProvider] = Depends(get_search_providers),
    geo_playbook: dict = Depends(get_geo_context),
) -> SearchResponse:
    if not settings.llm_configured:
        raise HTTPException(
            status_code=503,
            detail="The LLM provider is not configured on the server. Set ANTHROPIC_API_KEY in backend/.env.",
        )
    if not providers:
        raise HTTPException(
            status_code=503,
            detail="No search providers are configured. Set TAVILY_API_KEY or SERPER_API_KEY.",
        )
    try:
        return await run_search(
            db,
            brief=payload.brief,
            limit=payload.limit,
            force_refresh=payload.force_refresh,
            settings=settings,
            llm=llm,
            providers=providers,
            geo_playbook=geo_playbook,
        )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - last-resort guard; details are logged, not leaked
        logger.exception("Search failed for brief=%r", payload.brief[:120])
        raise HTTPException(status_code=500, detail="Search failed due to an internal error.")
