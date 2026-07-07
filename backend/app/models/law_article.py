from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.law import Law
    from app.models.law_article_version import LawArticleVersion
    from app.models.procedure_legal_reference import ProcedureLegalReference


class LawArticle(Base):
    __tablename__ = "law_articles"
    __table_args__ = (
        Index("ix_law_articles_law_id", "law_id"),
        Index("ix_law_articles_mapping_status", "mapping_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    law_id: Mapped[int] = mapped_column(ForeignKey("laws.id"), nullable=False)
    article_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    article_number_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    article_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mapping_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="TODO_MOLEG_API_ARTICLE_CHECK",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    law: Mapped["Law"] = relationship(back_populates="articles")
    versions: Mapped[list["LawArticleVersion"]] = relationship(back_populates="law_article")
    procedure_references: Mapped[list["ProcedureLegalReference"]] = relationship(back_populates="law_article")
