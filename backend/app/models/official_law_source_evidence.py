from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.official_law_ingest_run import OfficialLawIngestRun


class OfficialLawSourceEvidence(Base):
    __tablename__ = "official_law_source_evidence"
    __table_args__ = (
        Index("ix_official_law_source_evidence_ingest_run_id", "ingest_run_id"),
        Index("ix_official_law_source_evidence_evidence_type", "evidence_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ingest_run_id: Mapped[int] = mapped_column(ForeignKey("official_law_ingest_runs.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sanitized_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redaction_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ingest_run: Mapped["OfficialLawIngestRun"] = relationship(back_populates="evidence_items")
