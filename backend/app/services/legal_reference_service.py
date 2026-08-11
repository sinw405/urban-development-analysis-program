from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.procedure_legal_reference import ProcedureLegalReference
from app.schemas.analyze import AnalyzeResponse, LegalReference, LegalReferenceVersion
from app.services.law_version_service import VERSION_STATUS_CURRENT, get_article_versions

PENDING_MOLEG_API_MAPPING = "PENDING_MOLEG_API_MAPPING"
TODO_MOLEG_API_ARTICLE_CHECK = "TODO_MOLEG_API_ARTICLE_CHECK"
EXPERT_REVIEW_REQUIRED = "EXPERT_REVIEW_REQUIRED"

LEGAL_REFERENCE_QUALITY_CANDIDATE = "candidate"
LEGAL_REFERENCE_QUALITY_VERIFIED = "verified"
LEGAL_REFERENCE_QUALITY_MISSING = "missing"

LEGAL_REFERENCE_PENDING_STATUSES = {
    PENDING_MOLEG_API_MAPPING,
    TODO_MOLEG_API_ARTICLE_CHECK,
    EXPERT_REVIEW_REQUIRED,
}



def _reference_quality(reference: ProcedureLegalReference) -> str:
    notes = reference.notes_json or {}
    quality = notes.get("reference_quality")
    if quality in {LEGAL_REFERENCE_QUALITY_CANDIDATE, LEGAL_REFERENCE_QUALITY_VERIFIED}:
        return quality
    if reference.reference_status == LEGAL_REFERENCE_QUALITY_VERIFIED:
        return LEGAL_REFERENCE_QUALITY_VERIFIED
    return LEGAL_REFERENCE_QUALITY_CANDIDATE


def _step_reference_status(references: list[LegalReference]) -> str:
    if not references:
        return LEGAL_REFERENCE_QUALITY_MISSING
    if all(reference.reference_quality == LEGAL_REFERENCE_QUALITY_VERIFIED for reference in references):
        return LEGAL_REFERENCE_QUALITY_VERIFIED
    return LEGAL_REFERENCE_QUALITY_CANDIDATE

def empty_legal_references() -> list[LegalReference]:
    return []


def is_pending_legal_reference_status(status: str) -> bool:
    return status in LEGAL_REFERENCE_PENDING_STATUSES or status.startswith(("TODO", "PENDING"))


def _version_reference(item) -> LegalReferenceVersion:
    version = item.version
    return LegalReferenceVersion(
        version_id=version.id,
        version_status=version.version_status,
        temporal_status=item.temporal_status,
        effective_date=version.effective_date,
        source=version.source,
    )


def _serialize_procedure_reference(
    db: Session,
    reference: ProcedureLegalReference,
    as_of: date | None,
) -> LegalReference:
    law = reference.law
    law_article = reference.law_article
    version_references: list[LegalReferenceVersion] = []
    current_version: LegalReferenceVersion | None = None

    if law_article is not None:
        version_references = [
            _version_reference(item) for item in get_article_versions(db=db, article_id=law_article.id, as_of=as_of)
        ]
        current_version = next(
            (version for version in version_references if version.temporal_status == VERSION_STATUS_CURRENT),
            None,
        )

    return LegalReference(
        step_code=reference.step_code,
        reference_status=reference.reference_status,
        reference_quality=_reference_quality(reference),
        placeholder=reference.placeholder,
        law_id=None if law is None else law.id,
        law_key=None if law is None else law.law_key,
        law_mapping_status=None if law is None else law.mapping_status,
        article_id=None if law_article is None else law_article.id,
        article_key=None if law_article is None else law_article.article_key,
        article_mapping_status=None if law_article is None else law_article.mapping_status,
        current_version=current_version,
        versions=version_references,
        notes=reference.notes_json or {},
    )


def get_legal_references_by_step_code(
    db: Session,
    step_codes: list[str],
    as_of: date | None = None,
) -> dict[str, list[LegalReference]]:
    if not step_codes:
        return {}

    statement = (
        select(ProcedureLegalReference)
        .options(
            joinedload(ProcedureLegalReference.law),
            joinedload(ProcedureLegalReference.law_article),
        )
        .where(ProcedureLegalReference.step_code.in_(step_codes))
        .order_by(ProcedureLegalReference.step_code, ProcedureLegalReference.id)
    )

    references_by_step_code: dict[str, list[LegalReference]] = {}
    for reference in db.scalars(statement).all():
        references_by_step_code.setdefault(reference.step_code, []).append(
            _serialize_procedure_reference(db=db, reference=reference, as_of=as_of)
        )
    return references_by_step_code


def attach_legal_references(
    db: Session,
    result: AnalyzeResponse,
    as_of: date | None = None,
) -> AnalyzeResponse:
    reference_as_of = as_of if as_of is not None else result.as_of
    references_by_step_code = get_legal_references_by_step_code(
        db=db,
        step_codes=[step.step_code for step in result.procedures],
        as_of=reference_as_of,
    )

    for step in result.procedures:
        step.legal_references = references_by_step_code.get(step.step_code, [])
        step.legal_reference_status = _step_reference_status(step.legal_references)
    return result


def attach_assessment_legal_references(
    db: Session,
    result: AnalyzeResponse,
    as_of: date | None = None,
) -> AnalyzeResponse:
    reference_as_of = as_of if as_of is not None else result.as_of
    codes = [item.assessment_code for item in result.assessments if item.assessment_code]
    references_by_code = get_legal_references_by_step_code(
        db=db, step_codes=codes, as_of=reference_as_of
    )

    for item in result.assessments:
        item.as_of = reference_as_of
        item.legal_references = references_by_code.get(item.assessment_code or "", [])
        if item.legal_references:
            item.legal_basis_status = _step_reference_status(item.legal_references)
    return result
