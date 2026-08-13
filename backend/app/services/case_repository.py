from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.development_case import DevelopmentCase
from app.models.project import Project


def project_exists(db: Session, project_id: int) -> bool:
    return db.scalar(select(Project.id).where(Project.id == project_id)) is not None


def list_cases(db: Session) -> list[DevelopmentCase]:
    statement = select(DevelopmentCase).order_by(
        DevelopmentCase.created_at.desc(), DevelopmentCase.id.desc()
    )
    return list(db.scalars(statement).all())
