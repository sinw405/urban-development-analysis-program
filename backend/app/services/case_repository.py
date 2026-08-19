from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.development_case import DevelopmentCase
from app.models.project import Project
from app.schemas.cases import CaseCreate


def project_exists(db: Session, project_id: int) -> bool:
    return db.scalar(select(Project.id).where(Project.id == project_id)) is not None


def list_cases(db: Session) -> list[DevelopmentCase]:
    statement = select(DevelopmentCase).order_by(
        DevelopmentCase.created_at.desc(), DevelopmentCase.id.desc()
    )
    return list(db.scalars(statement).all())


def get_case(db: Session, case_id: int) -> DevelopmentCase | None:
    return db.get(DevelopmentCase, case_id)


def create_case(db: Session, payload: CaseCreate) -> DevelopmentCase:
    case = DevelopmentCase(**payload.model_dump(mode='json'))
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def update_case(db: Session, case: DevelopmentCase, payload: CaseCreate) -> DevelopmentCase:
    for field, value in payload.model_dump(mode='json').items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    return case
