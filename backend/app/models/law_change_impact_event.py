from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LawChangeImpactEvent(Base):
    __tablename__ = "law_change_impact_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_law_change_impact_events_idempotency_key"),
        Index("ix_law_change_impact_events_law_id", "law_id"),
        Index("ix_law_change_impact_events_to_mst", "to_mst"),
        Index("ix_law_change_impact_events_change_type", "change_type"),
        Index("ix_law_change_impact_events_impact_level", "impact_level"),
        Index("ix_law_change_impact_events_review_status", "derived_review_status"),
        Index("ix_law_change_impact_events_detected_at", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False)
    law_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_mst: Mapped[str] = mapped_column(String(100), nullable=False)
    to_mst: Mapped[str] = mapped_column(String(100), nullable=False)
    from_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    to_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    article_stable_id: Mapped[str] = mapped_column(String(255), nullable=False)
    article_no: Mapped[str] = mapped_column(String(100), nullable=False)
    article_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    affected_procedure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    affected_procedure_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("procedure_official_article_candidates.id", ondelete="CASCADE"), nullable=True)
    mapping_id: Mapped[int | None] = mapped_column(nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_mapping_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    derived_review_status: Mapped[str] = mapped_column(String(100), nullable=False)
    impact_level: Mapped[str] = mapped_column(String(50), nullable=False)
    impact_reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    official_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_url_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unavailable")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="pending_review")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
