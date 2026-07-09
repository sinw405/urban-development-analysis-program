from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.official_law_source import (
    LegalReferenceVerifyPreviewRequest,
    LegalReferenceVerifyPreviewResponse,
    MolegDiagnosticResult,
    MolegLiveDiagnosticResult,
    MolegTransportDiagnosticResponse,
    OfficialLawIngestPreviewRequest,
    OfficialLawIngestPreviewResponse,
    OfficialLawManualImportRequest,
    OfficialLawManualImportResponse,
    OfficialLawSnapshotStatusResponse,
)
from app.services.legal_reference_verification_service import list_verification_previews
from app.services.moleg_diagnostic_service import diagnose_moleg_connectivity, diagnose_moleg_live_only
from app.services.moleg_transport_probe_service import diagnose_moleg_transport
from app.services.official_law_db_source_service import get_official_law_snapshot_status
from app.services.official_law_manual_import_service import import_official_law_file
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


@router.get("/legal-references/moleg-live-diagnostic", response_model=MolegLiveDiagnosticResult)
def diagnose_moleg_live_source() -> MolegLiveDiagnosticResult:
    return diagnose_moleg_live_only()


@router.get("/legal-references/moleg-transport-diagnostic", response_model=MolegTransportDiagnosticResponse)
def diagnose_moleg_transport_source() -> MolegTransportDiagnosticResponse:
    return diagnose_moleg_transport()


@router.get("/legal-references/official-law-snapshot", response_model=OfficialLawSnapshotStatusResponse)
def get_official_law_snapshot(db: Session = Depends(get_db)) -> OfficialLawSnapshotStatusResponse:
    return get_official_law_snapshot_status(db=db)


@router.post("/legal-references/official-law-manual-import", response_model=OfficialLawManualImportResponse)
def import_official_law_manual_file(
    request: OfficialLawManualImportRequest,
    db: Session = Depends(get_db),
) -> OfficialLawManualImportResponse:
    return import_official_law_file(
        db=db,
        file_path=request.file_path,
        query=request.query,
        source_provider=request.source_provider,
        source_mode=request.source_mode,
    )


@router.post("/legal-references/official-laws/ingest-preview", response_model=OfficialLawIngestPreviewResponse)
def ingest_official_law_preview(
    request: OfficialLawIngestPreviewRequest,
    db: Session = Depends(get_db),
) -> OfficialLawIngestPreviewResponse:
    return ingest_live_document_preview(db=db, query=request.query)
