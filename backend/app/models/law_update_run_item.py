from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class LawUpdateRunItem(Base):
    __tablename__ = "law_update_run_items"
    __table_args__ = (Index("ix_law_update_run_items_run_law", "run_id", "law_identifier"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("law_update_runs.id", ondelete="CASCADE"), nullable=False)
    registry_id: Mapped[int | None] = mapped_column(ForeignKey("law_update_registry.id", ondelete="SET NULL"))
    law_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    from_mst: Mapped[str | None] = mapped_column(String(100))
    to_mst: Mapped[str | None] = mapped_column(String(100))
    version_changed: Mapped[bool | None] = mapped_column(Boolean)
    content_changed: Mapped[bool | None] = mapped_column(Boolean)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("live_law_change_events.id", ondelete="SET NULL"))
    event_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    sanitized_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())