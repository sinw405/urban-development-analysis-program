from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.official_law_source import (
    LegalReferenceVerifyPreviewRequest,
    LegalReferenceVerifyPreviewResponse,
    MolegDiagnosticResult,
    OfficialLawIngestPreviewRequest,
    OfficialLawIngestPreviewResponse,
    OfficialLawSnapshotStatusResponse,
)
from app.services.legal_reference_verification_service import list_verification_previews
from app.services.moleg_diagnostic_service import diagnose_moleg_connectivity
from app.services.official_law_db_source_service import get_official_law_snapshot_status
from app.services.official_law_persistence_service import ingest_live_document_preview


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


@router.get("/legal-references/official-laws/diagnostic", response_model=MolegDiagnosticResult)
def diagnose_official_law_source() -> MolegDiagnosticResult:
    return diagnose_moleg_connectivity()


@router.get("/legal-references/official-law-snapshot", response_model=OfficialLawSnapshotStatusResponse)
def get_official_law_snapshot(db: Session = Depends(get_db)) -> OfficialLawSnapshotStatusResponse:
    return get_official_law_snapshot_status(db=db)


@router.post("/legal-references/official-laws/ingest-preview", response_model=OfficialLawIngestPreviewResponse)
def ingest_official_law_preview(
    request: OfficialLawIngestPreviewRequest,
    db: Session = Depends(get_db),
) -> OfficialLawIngestPreviewResponse:
    return ingest_live_document_preview(db=db, query=request.query)
