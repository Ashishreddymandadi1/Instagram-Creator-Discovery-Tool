"""SQLAlchemy ORM models. Case-study scope: lightly normalized, JSON text fields
where SQLite makes that simplest."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Creator(Base):
    __tablename__ = "creator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(120), unique=True, index=True)  # lowercase, no @
    instagram_url: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    geo_concepts_json: Mapped[str] = mapped_column(Text, default="[]")
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    evidence: Mapped[list["CreatorEvidence"]] = relationship(
        back_populates="creator", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["CreatorAnalysis"]] = relationship(
        back_populates="creator", cascade="all, delete-orphan"
    )


class CreatorEvidence(Base):
    __tablename__ = "creator_evidence"
    __table_args__ = (UniqueConstraint("creator_id", "source_url", name="uq_evidence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    synthetic: Mapped[bool] = mapped_column(default=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    creator: Mapped["Creator"] = relationship(back_populates="evidence")


class CreatorAnalysis(Base):
    """One LLM analysis + deterministic score, tied to the brief it ran for."""

    __tablename__ = "creator_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator.id"), index=True)
    search_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_run.id"), nullable=True, index=True
    )
    brief: Mapped[str] = mapped_column(Text)

    geo_search_relevance: Mapped[float] = mapped_column(Float)
    topic_relevance: Mapped[float] = mapped_column(Float)
    content_relevance: Mapped[float] = mapped_column(Float)
    creator_fit: Mapped[float] = mapped_column(Float)
    overall_score: Mapped[int] = mapped_column(Integer)

    content_summary: Mapped[str] = mapped_column(Text, default="Not available")
    explanation: Mapped[str] = mapped_column(Text, default="Not available")
    relevant_topics_json: Mapped[str] = mapped_column(Text, default="[]")
    geo_concepts_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    creator: Mapped["Creator"] = relationship(back_populates="analyses")
    evidence_links: Mapped[list["AnalysisEvidence"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class AnalysisEvidence(Base):
    """Links one CreatorAnalysis to the exact CreatorEvidence rows that supported
    it. This scopes displayed provenance to the analysis that produced a score,
    rather than every source ever seen for the creator."""

    __tablename__ = "analysis_evidence"
    __table_args__ = (
        UniqueConstraint("analysis_id", "evidence_id", name="uq_analysis_evidence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("creator_analysis.id"), index=True
    )
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("creator_evidence.id"), index=True
    )

    analysis: Mapped["CreatorAnalysis"] = relationship(back_populates="evidence_links")
    evidence: Mapped["CreatorEvidence"] = relationship()


class SearchRun(Base):
    __tablename__ = "search_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brief: Mapped[str] = mapped_column(Text)
    normalized_brief: Mapped[str] = mapped_column(Text, index=True)
    criteria_json: Mapped[str] = mapped_column(Text, default="{}")
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    returned_count: Mapped[int] = mapped_column(Integer, default=0)
    data_status: Mapped[str] = mapped_column(String(20), default="live")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class SearchResult(Base):
    """Ordered creator ids returned for a run — powers cached replay."""

    __tablename__ = "search_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_run_id: Mapped[int] = mapped_column(ForeignKey("search_run.id"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator.id"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("creator_analysis.id"))
    rank: Mapped[int] = mapped_column(Integer)
