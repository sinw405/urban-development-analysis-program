from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LawUpdateEvent(Base):
    __tablename__ = "law_update_events"
    __table_args__ = (
        Index("ix_law_update_events_law_id", "law_id"),
        Index("ix_law_update_events_article_id", "article_id"),
        Index("ix_law_update_events_detected_at", "detected_at"),
        Index("ix_law_update_events_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    law_id: Mapped[int] = mapped_column(ForeignKey("laws.id"), nullable=False)
    article_id: Mapped[int] = mapped_column(ForeignKey("law_articles.id"), nullable=False)
    previous_version_id: Mapped[int | None] = mapped_column(ForeignKey("law_article_versions.id"), nullable=True)
    new_version_id: Mapped[int | None] = mapped_column(ForeignKey("law_article_versions.id"), nullable=True)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="PENDING_REVIEW")
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="MOLEG")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
