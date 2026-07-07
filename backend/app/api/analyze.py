from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_repository import create_project_with_analysis
from app.services.analyzer import analyze_project
from app.services.legal_reference_service import attach_legal_references


router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    result = analyze_project(request)
    attach_legal_references(db=db, result=result, as_of=request.as_of)
    result.warnings.append("Analysis request and result were stored in PostgreSQL.")
    analysis = create_project_with_analysis(
        db=db,
        request=request,
        result=result,
        rule_version="Phase 1 YAML placeholder rules",
    )

    result.project_id = analysis.project_id
    result.analysis_id = analysis.id
    result.created_at = analysis.created_at
    return result
