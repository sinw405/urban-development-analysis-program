from datetime import date, datetime
from typing import Any, TYPE_CHECKING
from sqlalchemy import Boolean, Date, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
if TYPE_CHECKING:
    from app.models.live_law_change_event_audit import LiveLawChangeEventAudit
class LiveLawChangeEvent(Base):
    __tablename__ = "live_law_change_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_live_law_change_events_idempotency_key"), Index("ix_live_law_change_events_law_msts", "law_id", "from_mst", "to_mst"), Index("ix_live_law_change_events_analysis_status", "analysis_status"))
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="MOLEG")
    law_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False)
    from_mst: Mapped[str] = mapped_column(String(100), nullable=False)
    to_mst: Mapped[str] = mapped_column(String(100), nullable=False)
    from_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    to_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version_changed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    content_changed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impacted_rule_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changed_articles_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    impacted_rules_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sanitized_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    audits: Mapped[list["LiveLawChangeEventAudit"]] = relationship(back_populates="event", cascade="all, delete-orphan")
