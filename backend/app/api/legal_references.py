from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.official_law_source import LegalReferenceVerifyPreviewRequest, LegalReferenceVerifyPreviewResponse
from app.services.legal_reference_verification_service import list_verification_previews


router = APIRouter(tags=["legal-references"])


@router.post("/legal-references/verify-preview", response_model=LegalReferenceVerifyPreviewResponse)
def verify_legal_references_preview(
    request: LegalReferenceVerifyPreviewRequest,
    db: Session = Depends(get_db),
) -> LegalReferenceVerifyPreviewResponse:
    return LegalReferenceVerifyPreviewResponse(
        items=list_verification_previews(
            db=db,
            procedure_reference_ids=request.procedure_reference_ids,
            source_mode=request.source_mode,
        )
    )
