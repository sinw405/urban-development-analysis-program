from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProcedureArticleReviewEvent(Base):
    __tablename__ = "procedure_article_review_events"
    __table_args__ = (
        Index("ix_proc_article_review_events_candidate_id", "candidate_id"),
        Index("ix_proc_article_review_events_reviewed_at", "reviewed_at"),
        Index("ix_proc_article_review_events_new_status", "new_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("procedure_official_article_candidates.id", ondelete="CASCADE"), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(100), nullable=False)
    new_status: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    review_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_mst: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
