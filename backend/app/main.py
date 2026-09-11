"""GEO Creator Scout API — FastAPI app factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import creators, health, search
from app.config.settings import get_settings
from app.database import init_db

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("geo_creator_scout")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info(
        "GEO Creator Scout ready | llm_configured=%s | providers=%s",
        settings.llm_configured,
        settings.active_providers(),
    )
    yield


app = FastAPI(
    title="GEO Creator Scout API",
    version="1.0.0",
    description="Instagram creator discovery + GEO relevance ranking.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(creators.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "GEO Creator Scout", "docs": "/docs", "health": "/api/health"}
