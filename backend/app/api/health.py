"""GET /api/health — booleans only, never key values."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config.settings import Settings
from app.dependencies import get_app_settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_configured=settings.llm_configured,
        llm_model=settings.llm_model,
        search_providers=settings.active_providers(),
        cache_ttl_hours=settings.cache_ttl_hours,
    )
