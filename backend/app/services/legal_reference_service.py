from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.procedure_legal_reference import ProcedureLegalReference
from app.schemas.analyze import AnalyzeResponse

PENDING_MOLEG_API_MAPPING = "PENDING_MOLEG_API_MAPPING"
TODO_MOLEG_API_ARTICLE_CHECK = "TODO_MOLEG_API_ARTICLE_CHECK"
EXPERT_REVIEW_REQUIRED = "EXPERT_REVIEW_REQUIRED"

LEGAL_REFERENCE_PENDING_STATUSES = {
    PENDING_MOLEG_API_MAPPING,
    TODO_MOLEG_API_ARTICLE_CHECK,
    EXPERT_REVIEW_REQUIRED,
}


def empty_legal_references() -> list[dict[str, object]]:
    return []


def is_pending_legal_reference_status(status: str) -> bool:
    return status in LEGAL_REFERENCE_PENDING_STATUSES or status.startswith(("TODO", "PENDING"))


def _serialize_procedure_reference(reference: ProcedureLegalReference) -> dict[str, Any]:
    law = reference.law
    law_article = reference.law_article

    return {
        "step_code": reference.step_code,
        "reference_status": reference.reference_status,
        "placeholder": reference.placeholder,
        "law": None
        if law is None
        else {
            "id": law.id,
            "law_name": law.law_name,
            "law_key": law.law_key,
            "source": law.source,
            "mapping_status": law.mapping_status,
        },
        "law_article": None
        if law_article is None
        else {
            "id": law_article.id,
            "article_key": law_article.article_key,
            "article_number_text": law_article.article_number_text,
            "article_title": law_article.article_title,
            "mapping_status": law_article.mapping_status,
        },
        "notes": reference.notes_json or {},
    }


def get_legal_references_by_step_code(
    db: Session,
    step_codes: list[str],
) -> dict[str, list[dict[str, Any]]]:
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

    references_by_step_code: dict[str, list[dict[str, Any]]] = {}
    for reference in db.scalars(statement).all():
        references_by_step_code.setdefault(reference.step_code, []).append(_serialize_procedure_reference(reference))
    return references_by_step_code


def attach_legal_references(db: Session, result: AnalyzeResponse) -> AnalyzeResponse:
    references_by_step_code = get_legal_references_by_step_code(
        db=db,
        step_codes=[step.step_code for step in result.procedures],
    )

    for step in result.procedures:
        step.legal_references = references_by_step_code.get(step.step_code, [])
    return result
