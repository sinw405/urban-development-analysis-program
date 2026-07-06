from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analysis_history import (
    AnalysisDetail,
    AnalysisListResponse,
    AnalysisSort,
    AnalysisSummary,
)
from app.services.analysis_repository import get_analysis_result, list_analysis_results


router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.get("", response_model=AnalysisListResponse)
def list_analyses(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    project_name: str | None = None,
    local_government: str | None = None,
    sort: AnalysisSort = "created_at_desc",
    db: Session = Depends(get_db),
) -> AnalysisListResponse:
    analyses, total = list_analysis_results(
        db=db,
        limit=limit,
        offset=offset,
        project_name=project_name,
        local_government=local_government,
        sort=sort,
    )
    items = [
        AnalysisSummary(
            analysis_id=analysis.id,
            project_id=analysis.project_id,
            project_name=analysis.project.project_name,
            location=analysis.project.location,
            area_square_meters=analysis.project.area_square_meters,
            local_government=analysis.project.local_government,
            created_at=analysis.created_at,
        )
        for analysis in analyses
    ]
    return AnalysisListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)) -> AnalysisDetail:
    analysis = get_analysis_result(db, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis result not found")

    return AnalysisDetail(
        analysis_id=analysis.id,
        project_id=analysis.project_id,
        project_name=analysis.project.project_name,
        request_payload=analysis.request_payload,
        result_payload=analysis.result_payload,
        rule_version=analysis.rule_version,
        created_at=analysis.created_at,
    )
