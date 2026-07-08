from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.official_law_article import OfficialLawArticleRecord


class OfficialLawDocument(Base):
    __tablename__ = "official_law_documents"
    __table_args__ = (
        UniqueConstraint(
            "source_provider",
            "law_id",
            "mst",
            "enforcement_date",
            name="uq_official_law_documents_provider_law_mst_enforcement",
        ),
        Index("ix_official_law_documents_law_title", "law_title"),
        Index("ix_official_law_documents_law_id", "law_id"),
        Index("ix_official_law_documents_mst", "mst"),
        Index("ix_official_law_documents_enforcement_date", "enforcement_date"),
        Index("ix_official_law_documents_is_current", "is_current"),
        Index("ix_official_law_documents_document_status", "document_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    law_title: Mapped[str] = mapped_column(String(255), nullable=False)
    law_short_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    law_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mst: Mapped[str | None] = mapped_column(String(100), nullable=True)
    promulgation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    enforcement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    document_status: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sanitized_source_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    articles: Mapped[list["OfficialLawArticleRecord"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
