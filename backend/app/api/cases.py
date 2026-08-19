from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.cases import (
    CaseComparisonItem,
    CaseComparisonResponse,
    CaseCreate,
    CaseDetail,
    CaseUpdate,
)
from app.services.case_repository import (
    create_case,
    get_case,
    list_cases,
    project_exists,
    update_case,
)


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


@router.post('', response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
def register_case(payload: CaseCreate, db: Session = Depends(get_db)) -> CaseDetail:
    return CaseDetail.model_validate(create_case(db, payload))


@router.get('/{case_id}', response_model=CaseDetail)
def read_case(case_id: int, db: Session = Depends(get_db)) -> CaseDetail:
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail='Case not found')
    return CaseDetail.model_validate(case)


@router.patch('/{case_id}', response_model=CaseDetail)
def patch_case(case_id: int, payload: CaseUpdate, db: Session = Depends(get_db)) -> CaseDetail:
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail='Case not found')
    merged = {
        'name': case.name,
        'location': case.location,
        'area_m2': case.area_m2,
        'method': case.method,
        'operator_type': case.operator_type,
        'timeline': case.timeline,
        'history': case.history,
        'data_classification': case.data_classification,
        'provenance': case.provenance,
    }
    merged.update(payload.model_dump(exclude_unset=True, mode='json'))
    try:
        validated = CaseCreate.model_validate(merged)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc
    return CaseDetail.model_validate(update_case(db, case, validated))
