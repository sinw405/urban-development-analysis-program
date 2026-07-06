from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.analysis_result import AnalysisResult
from app.models.project import Project
from app.schemas.analysis_history import AnalysisSort
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


def _apply_analysis_filters(
    statement: Select,
    project_name: str | None,
    local_government: str | None,
) -> Select:
    if project_name:
        statement = statement.where(Project.project_name.ilike(f"%{project_name}%"))
    if local_government:
        statement = statement.where(Project.local_government.ilike(f"%{local_government}%"))
    return statement


def list_analysis_results(
    db: Session,
    limit: int,
    offset: int,
    project_name: str | None = None,
    local_government: str | None = None,
    sort: AnalysisSort = "created_at_desc",
) -> tuple[list[AnalysisResult], int]:
    base_statement = select(AnalysisResult).join(AnalysisResult.project)
    base_statement = _apply_analysis_filters(base_statement, project_name, local_government)

    count_statement = select(func.count()).select_from(base_statement.order_by(None).subquery())
    total = db.scalar(count_statement) or 0

    if sort == "created_at_asc":
        order_by = (AnalysisResult.created_at.asc(), AnalysisResult.id.asc())
    else:
        order_by = (AnalysisResult.created_at.desc(), AnalysisResult.id.desc())

    list_statement = (
        base_statement
        .options(joinedload(AnalysisResult.project))
        .order_by(*order_by)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(list_statement).all()), total


def get_analysis_result(db: Session, analysis_id: int) -> AnalysisResult | None:
    statement = (
        select(AnalysisResult)
        .options(joinedload(AnalysisResult.project))
        .where(AnalysisResult.id == analysis_id)
    )
    return db.scalar(statement)
