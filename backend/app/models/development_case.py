from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DevelopmentCase(Base):
    __tablename__ = "development_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    operator_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    data_classification: Mapped[str] = mapped_column(
        String(50), nullable=False, default='UNVERIFIED', server_default='UNVERIFIED'
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
