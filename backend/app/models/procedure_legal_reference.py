from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.law import Law
    from app.models.law_article import LawArticle


class ProcedureLegalReference(Base):
    __tablename__ = "procedure_legal_references"
    __table_args__ = (
        Index("ix_procedure_legal_references_step_code", "step_code"),
        Index("ix_procedure_legal_references_reference_status", "reference_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    step_code: Mapped[str] = mapped_column(String(100), nullable=False)
    law_id: Mapped[int | None] = mapped_column(ForeignKey("laws.id"), nullable=True)
    law_article_id: Mapped[int | None] = mapped_column(ForeignKey("law_articles.id"), nullable=True)
    reference_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="TODO_MOLEG_API_ARTICLE_CHECK",
    )
    placeholder: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="TODO_MOLEG_API_ARTICLE_CHECK",
    )
    notes_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    law: Mapped["Law | None"] = relationship(back_populates="procedure_references")
    law_article: Mapped["LawArticle | None"] = relationship(back_populates="procedure_references")
