"""Creator endpoints: fetch one, refresh one."""
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
from app.models.db_models import Creator
from app.models.schemas import CreatorResult, RefreshResponse
from app.providers.base import SearchProvider
from app.services import creator_service
from app.services.llm_service import LLMService
from app.services.search_orchestrator import refresh_creator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/creators", tags=["creators"])


@router.get("/{creator_id}", response_model=CreatorResult)
def get_creator(creator_id: int, db: Session = Depends(get_db)) -> CreatorResult:
    creator = db.get(Creator, creator_id)
    if creator is None:
        raise HTTPException(status_code=404, detail="Creator not found.")
    analysis = creator_service.latest_analysis_for_creator(db, creator_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis exists for this creator yet.")
    return creator_service.to_creator_result(creator, analysis, "cached")


@router.post("/{creator_id}/refresh", response_model=RefreshResponse)
async def refresh(
    creator_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    llm: LLMService = Depends(get_llm_service),
    providers: list[SearchProvider] = Depends(get_search_providers),
    geo_playbook: dict = Depends(get_geo_context),
) -> RefreshResponse:
    if not settings.llm_configured:
        raise HTTPException(status_code=503, detail="The LLM provider is not configured on the server.")
    try:
        result = await refresh_creator(
            db,
            creator_id=creator_id,
            settings=settings,
            llm=llm,
            providers=providers,
            geo_playbook=geo_playbook,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Refresh failed for creator_id=%s", creator_id)
        raise HTTPException(status_code=500, detail="Refresh failed due to an internal error.")
    if result is None:
        raise HTTPException(status_code=404, detail="Creator not found.")
    return result
