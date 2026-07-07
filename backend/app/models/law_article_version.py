from datetime import date, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.law_article import LawArticle


class LawArticleVersion(Base):
    __tablename__ = "law_article_versions"
    __table_args__ = (
        Index("ix_law_article_versions_law_article_id", "law_article_id"),
        Index("ix_law_article_versions_version_status", "version_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    law_article_id: Mapped[int] = mapped_column(ForeignKey("law_articles.id"), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    article_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="MOLEG")
    version_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="PENDING_MOLEG_API_MAPPING",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    law_article: Mapped["LawArticle"] = relationship(back_populates="versions")
