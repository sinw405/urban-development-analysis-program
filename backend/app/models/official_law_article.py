from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.official_law_document import OfficialLawDocument


class OfficialLawArticleRecord(Base):
    __tablename__ = "official_law_articles"
    __table_args__ = (
        Index("ix_official_law_articles_document_id", "document_id"),
        Index("ix_official_law_articles_article_no", "article_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("official_law_documents.id"), nullable=False)
    article_no: Mapped[str] = mapped_column(String(100), nullable=False)
    article_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    article_text: Mapped[str] = mapped_column(Text, nullable=False)
    paragraphs_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_anchor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    document: Mapped["OfficialLawDocument"] = relationship(back_populates="articles")
