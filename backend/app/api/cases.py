from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.cases import CaseComparisonItem, CaseComparisonResponse
from app.services.case_repository import list_cases, project_exists


router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=CaseComparisonResponse)
def get_cases(
    similar_to: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> CaseComparisonResponse:
    if not project_exists(db, similar_to):
        raise HTTPException(status_code=404, detail="Project not found")
    return CaseComparisonResponse(
        items=[CaseComparisonItem.model_validate(item) for item in list_cases(db)]
    )
