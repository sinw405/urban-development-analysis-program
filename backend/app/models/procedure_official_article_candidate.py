from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProcedureOfficialArticleCandidate(Base):
    __tablename__ = "procedure_official_article_candidates"
    __table_args__ = (
        UniqueConstraint(
            "procedure_code",
            "article_id",
            "match_method",
            "source_mode_detail",
            name="uq_proc_article_candidate_step_article_source",
        ),
        Index("ix_proc_article_candidates_procedure_code", "procedure_code"),
        Index("ix_proc_article_candidates_law_title", "law_title"),
        Index("ix_proc_article_candidates_law_id", "law_id"),
        Index("ix_proc_article_candidates_article_id", "article_id"),
        Index("ix_proc_article_candidates_match_status", "match_status"),
        Index("ix_proc_article_candidates_source_mode_detail", "source_mode_detail"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    procedure_code: Mapped[str] = mapped_column(String(100), nullable=False)
    procedure_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    law_title: Mapped[str] = mapped_column(String(255), nullable=False)
    law_short_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    law_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mst: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("official_law_documents.id"), nullable=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("official_law_articles.id"), nullable=True)
    article_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    article_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    article_anchor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_method: Mapped[str] = mapped_column(String(100), nullable=False)
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    match_status: Mapped[str] = mapped_column(String(100), nullable=False, default="candidate")
    source_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    source_mode_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_level: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    document = relationship("OfficialLawDocument")
    article = relationship("OfficialLawArticleRecord")

