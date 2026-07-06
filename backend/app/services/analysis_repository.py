from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.analysis_result import AnalysisResult
from app.models.project import Project
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse


def create_project_with_analysis(
    db: Session,
    request: AnalyzeRequest,
    result: AnalyzeResponse,
    rule_version: str | None = None,
) -> AnalysisResult:
    project = Project(
        project_name=request.project_name,
        location=request.location,
        area_square_meters=request.area_square_meters,
        implementation_method=request.implementation_method,
        implementer_type=request.implementer_type,
        local_government=request.local_government,
    )
    db.add(project)
    db.flush()

    analysis = AnalysisResult(
        project_id=project.id,
        request_payload=request.model_dump(mode="json"),
        result_payload=result.model_dump(mode="json"),
        rule_version=rule_version,
    )
    db.add(analysis)
    db.flush()

    result.project_id = project.id
    result.analysis_id = analysis.id
    analysis.result_payload = result.model_dump(mode="json")

    db.commit()
    db.refresh(analysis)
    db.refresh(project)

    result.created_at = analysis.created_at
    analysis.result_payload = result.model_dump(mode="json")
    db.commit()
    db.refresh(analysis)
    return analysis


def list_analysis_results(db: Session) -> list[AnalysisResult]:
    statement = (
        select(AnalysisResult)
        .options(joinedload(AnalysisResult.project))
        .order_by(AnalysisResult.created_at.desc(), AnalysisResult.id.desc())
    )
    return list(db.scalars(statement).all())


def get_analysis_result(db: Session, analysis_id: int) -> AnalysisResult | None:
    statement = (
        select(AnalysisResult)
        .options(joinedload(AnalysisResult.project))
        .where(AnalysisResult.id == analysis_id)
    )
    return db.scalar(statement)
