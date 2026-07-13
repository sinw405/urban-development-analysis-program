from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import LawChangeImpactEvent, OfficialLawArticleRecord, OfficialLawDocument, ProcedureArticleReviewEvent, ProcedureOfficialArticleCandidate
from app.services.rule_loader import load_yaml_rule

REVIEW_SOURCE_CONFIRMED = "manual_review_confirmed"
REVIEW_SOURCE_REJECTED = "manual_review_rejected"
REVIEW_SOURCE_REOPENED = "manual_review_reopened"
STATUS_CONFIRMED = "confirmed"
STATUS_REJECTED = "rejected"
STATUS_UNCONFIRMED = "unconfirmed"
STATUS_NEEDS_REVALIDATION = "needs_revalidation"
STATUS_STALE = "stale"


@dataclass
class ReviewActionResult:
    status: str
    candidate_id: int | None = None
    previous_status: str | None = None
    new_status: str | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None
    rollback: bool = False
    secret_exposed: bool = False
    raw_payload_stored: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


def list_review_candidates(db: Session, status: str | None = None) -> list[dict[str, Any]]:
    rows = db.scalars(_candidate_statement().order_by(ProcedureOfficialArticleCandidate.procedure_code, ProcedureOfficialArticleCandidate.id)).all()
    items = [candidate_detail(db, row.id, include_article_text=False) for row in rows]
    return [item for item in items if status is None or item["candidate_status"] == status]


def candidate_detail(db: Session, candidate_id: int, include_article_text: bool = True) -> dict[str, Any]:
    candidate = db.scalar(_candidate_statement().where(ProcedureOfficialArticleCandidate.id == candidate_id))
    if candidate is None:
        raise ValueError("candidate_not_found")
    config = _procedure_config(candidate.procedure_code)
    document = candidate.document
    article = candidate.article
    current_document = _current_document(db, candidate.law_id)
    status = _candidate_detail_status(db, candidate, current_document)
    official_url = None
    official_url_status = "unavailable"
    if document is not None and document.sanitized_source_url:
        official_url = document.sanitized_source_url
        official_url_status = "available"
    detail = {
        "candidate_id": candidate.id,
        "procedure_code": candidate.procedure_code,
        "procedure_name": candidate.procedure_name,
        "procedure_description": config.get("description"),
        "procedure_rule_source": "procedure_article_keywords.yaml",
        "candidate_status": status,
        "match_status": candidate.match_status,
        "match_method": candidate.match_method,
        "match_score": candidate.match_score,
        "confidence_level": candidate.confidence_level,
        "provider_reason": candidate.provider_reason,
        "law_title": candidate.law_title,
        "law_id": candidate.law_id,
        "mst": candidate.mst,
        "effective_date": None if document is None or document.enforcement_date is None else str(document.enforcement_date),
        "current_mst": None if current_document is None else current_document.mst,
        "current_effective_date": None if current_document is None or current_document.enforcement_date is None else str(current_document.enforcement_date),
        "article_id": candidate.article_id,
        "article_no": candidate.article_no,
        "article_title": candidate.article_title,
        "article_anchor": candidate.article_anchor,
        "article_text": None if not include_article_text or article is None else article.article_text,
        "official_url": official_url,
        "official_url_status": official_url_status,
        "source_mode": candidate.source_mode,
        "source_mode_detail": candidate.source_mode_detail,
        "reviewer": candidate.confirmed_by,
        "reviewed_at": None if candidate.confirmed_at is None else candidate.confirmed_at.isoformat(),
        "review_note": candidate.confirmation_note,
        "confirmed_under_mst": candidate.mst if candidate.is_confirmed else None,
        "reviewed_law_id": candidate.law_id if candidate.confirmed_source else None,
        "reviewed_effective_date": None if not candidate.confirmed_source or document is None or document.enforcement_date is None else str(document.enforcement_date),
        "review_required": status in {STATUS_UNCONFIRMED, STATUS_NEEDS_REVALIDATION, STATUS_STALE},
        "applicable": status == STATUS_CONFIRMED,
        "secret_exposed": False,
        "raw_payload_stored": False,
    }
    return detail


def confirm_candidate(db: Session, candidate_id: int, reviewer: str | None, note: str | None, force_rollback: bool = False) -> ReviewActionResult:
    return _review_action(db, candidate_id, reviewer, note, REVIEW_SOURCE_CONFIRMED, True, STATUS_CONFIRMED, force_rollback)


def reject_candidate(db: Session, candidate_id: int, reviewer: str | None, note: str | None, force_rollback: bool = False) -> ReviewActionResult:
    return _review_action(db, candidate_id, reviewer, note, REVIEW_SOURCE_REJECTED, False, STATUS_REJECTED, force_rollback)


def reopen_candidate(db: Session, candidate_id: int, reviewer: str | None, note: str | None, force_rollback: bool = False) -> ReviewActionResult:
    return _review_action(db, candidate_id, reviewer, note, REVIEW_SOURCE_REOPENED, False, STATUS_UNCONFIRMED, force_rollback)


def candidate_review_status(candidate: ProcedureOfficialArticleCandidate, current_document: OfficialLawDocument | None = None) -> str:
    if candidate.confirmed_source == REVIEW_SOURCE_REJECTED:
        return STATUS_REJECTED
    if candidate.is_confirmed:
        if candidate.article is None:
            return STATUS_STALE
        if current_document is not None and candidate.mst and current_document.mst and candidate.mst != current_document.mst:
            return STATUS_NEEDS_REVALIDATION
        return STATUS_CONFIRMED
    return STATUS_UNCONFIRMED


def _candidate_detail_status(db: Session, candidate: ProcedureOfficialArticleCandidate, current_document: OfficialLawDocument | None) -> str:
    base_status = candidate_review_status(candidate, current_document)
    if base_status == STATUS_REJECTED:
        return base_status
    impact = db.scalar(
        select(LawChangeImpactEvent)
        .where(LawChangeImpactEvent.candidate_id == candidate.id)
        .order_by(LawChangeImpactEvent.detected_at.desc(), LawChangeImpactEvent.id.desc())
        .limit(1)
    )
    if impact is not None and impact.derived_review_status in {STATUS_NEEDS_REVALIDATION, STATUS_STALE}:
        return impact.derived_review_status
    return base_status
def _review_action(db: Session, candidate_id: int, reviewer: str | None, note: str | None, source: str, is_confirmed: bool, new_status: str, force_rollback: bool) -> ReviewActionResult:
    if not reviewer or not reviewer.strip():
        return ReviewActionResult(status="validation_error", candidate_id=candidate_id, errors=["reviewer_required"])
    if not note or not note.strip():
        return ReviewActionResult(status="validation_error", candidate_id=candidate_id, errors=["review_note_required"])
    candidate = db.scalar(_candidate_statement().where(ProcedureOfficialArticleCandidate.id == candidate_id))
    if candidate is None:
        return ReviewActionResult(status="not_found", candidate_id=candidate_id, errors=["candidate_not_found"])
    current_document = _current_document(db, candidate.law_id)
    previous = candidate_review_status(candidate, current_document)
    reviewed_at = datetime.now(UTC)
    clean_reviewer = reviewer.strip()
    clean_note = note.strip()
    try:
        candidate.is_confirmed = is_confirmed
        candidate.confirmed_at = reviewed_at
        candidate.confirmed_by = clean_reviewer
        candidate.confirmed_source = source
        candidate.confirmation_note = _append_review_note(candidate.confirmation_note, previous, new_status, clean_reviewer, clean_note, reviewed_at)
        db.add(
            ProcedureArticleReviewEvent(
                candidate_id=candidate.id,
                previous_status=previous,
                new_status=new_status,
                reviewer=clean_reviewer,
                review_note=clean_note,
                reviewed_at=reviewed_at,
                reviewed_mst=candidate.mst,
                reviewed_effective_date=None if candidate.document is None else candidate.document.enforcement_date,
                source=source,
                metadata_json={"raw_payload_stored": False, "secret_exposed": False},
            )
        )
        if force_rollback:
            raise RuntimeError("PHASE39_TEST_ROLLBACK")
        db.commit()
        db.refresh(candidate)
        return ReviewActionResult(status="ok", candidate_id=candidate.id, previous_status=previous, new_status=new_status, reviewer=candidate.confirmed_by, reviewed_at=candidate.confirmed_at.isoformat(), review_note=candidate.confirmation_note)
    except Exception as exc:
        db.rollback()
        return ReviewActionResult(status="rolled_back", candidate_id=candidate_id, previous_status=previous, new_status=new_status, reviewer=reviewer, rollback=True, errors=[exc.__class__.__name__])

def _append_review_note(existing: str | None, previous: str, new_status: str, reviewer: str, note: str, reviewed_at: datetime) -> str:
    entry = f"[{reviewed_at.isoformat()}] {previous} -> {new_status}; reviewer={reviewer}; note={note}"
    return entry if not existing else f"{existing}\n{entry}"


def _candidate_statement():
    return select(ProcedureOfficialArticleCandidate).options(joinedload(ProcedureOfficialArticleCandidate.document), joinedload(ProcedureOfficialArticleCandidate.article))


def _current_document(db: Session, law_id: str | None) -> OfficialLawDocument | None:
    if not law_id:
        return None
    return db.scalar(
        select(OfficialLawDocument)
        .where(OfficialLawDocument.law_id == law_id, OfficialLawDocument.source_mode == "live")
        .order_by(OfficialLawDocument.enforcement_date.desc().nullslast(), OfficialLawDocument.id.desc())
        .limit(1)
    )


def _procedure_config(procedure_code: str) -> dict[str, Any]:
    data = load_yaml_rule("procedure_article_keywords.yaml")
    for item in data.get("steps", []):
        if isinstance(item, dict) and item.get("procedure_code") == procedure_code:
            return item
    return {"procedure_code": procedure_code}
