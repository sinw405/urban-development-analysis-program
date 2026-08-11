from datetime import date, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.law import Law


class LawAttachedTableEvidence(Base):
    __tablename__ = "law_attached_table_evidence"
    __table_args__ = (
        UniqueConstraint("law_id", "table_key", "mst", name="uq_law_attached_table_evidence_version"),
        Index("ix_law_attached_table_evidence_as_of", "law_id", "effective_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    law_id: Mapped[int] = mapped_column(ForeignKey("laws.id", ondelete="CASCADE"), nullable=False)
    table_key: Mapped[str] = mapped_column(String(200), nullable=False)
    table_number: Mapped[str] = mapped_column(String(50), nullable=False)
    table_title: Mapped[str] = mapped_column(String(500), nullable=False)
    mst: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="MOLEG_LIVE")
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    law: Mapped["Law"] = relationship(back_populates="attached_table_evidence")
