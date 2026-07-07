from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.law_article import LawArticle
    from app.models.procedure_legal_reference import ProcedureLegalReference


class Law(Base):
    __tablename__ = "laws"
    __table_args__ = (
        Index("ix_laws_law_name", "law_name"),
        Index("ix_laws_mapping_status", "mapping_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False)
    law_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="MOLEG")
    mapping_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="PENDING_MOLEG_API_MAPPING",
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

    articles: Mapped[list["LawArticle"]] = relationship(back_populates="law")
    procedure_references: Mapped[list["ProcedureLegalReference"]] = relationship(back_populates="law")
