"""SQLite engine + session management. DB initializes automatically on startup."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import BACKEND_DIR, get_settings
from app.models.db_models import Base

logger = logging.getLogger(__name__)

_settings = get_settings()


def _resolve_sqlite_path(url: str) -> str:
    """Make a relative sqlite:///./data/... path absolute against backend/ and
    ensure the parent directory exists."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw = url[len(prefix):]
    p = Path(raw)
    if not p.is_absolute():
        p = (BACKEND_DIR / raw).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{p.as_posix()}"


DATABASE_URL = _resolve_sqlite_path(_settings.database_url)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at %s", DATABASE_URL)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
