from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.official_law_source_evidence import OfficialLawSourceEvidence


class OfficialLawIngestRun(Base):
    __tablename__ = "official_law_ingest_runs"
    __table_args__ = (
        Index("ix_official_law_ingest_runs_status", "status"),
        Index("ix_official_law_ingest_runs_query", "query"),
        Index("ix_official_law_ingest_runs_source_mode", "source_mode"),
        Index("ix_official_law_ingest_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    query: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    selected_law_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_law_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    selected_mst: Mapped[str | None] = mapped_column(String(100), nullable=True)
    candidate_count: Mapped[int] = mapped_column(nullable=False, default=0)
    article_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    evidence_items: Mapped[list["OfficialLawSourceEvidence"]] = relationship(
        back_populates="ingest_run",
        cascade="all, delete-orphan",
    )
