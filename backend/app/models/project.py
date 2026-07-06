from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.analysis_result import AnalysisResult


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("area_square_meters > 0", name="ck_projects_area_square_meters_positive"),
        Index("ix_projects_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255), index=True)
    location: Mapped[str] = mapped_column(String(500))
    area_square_meters: Mapped[float] = mapped_column(Float)
    implementation_method: Mapped[str] = mapped_column(String(255))
    implementer_type: Mapped[str] = mapped_column(String(255))
    local_government: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analyses: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
