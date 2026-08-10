from datetime import datetime
from typing import Any, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
if TYPE_CHECKING:
    from app.models.live_law_change_event import LiveLawChangeEvent
class LiveLawChangeEventAudit(Base):
    __tablename__ = "live_law_change_event_audits"
    __table_args__ = (Index("ix_live_law_change_event_audits_event_created", "event_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("live_law_change_events.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    sanitized_detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    event: Mapped["LiveLawChangeEvent"] = relationship(back_populates="audits")
