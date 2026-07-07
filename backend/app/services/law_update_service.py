from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LawArticle, LawArticleVersion, LawUpdateEvent, ProcedureLegalReference
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING

CHANGE_TYPE_NEW_VERSION = "NEW_VERSION"
CHANGE_TYPE_CONTENT_CHANGED = "CONTENT_CHANGED"
EVENT_STATUS_PENDING_REVIEW = "PENDING_REVIEW"


@dataclass(frozen=True)
class IncomingArticleVersionPayload:
    article_id: int
    effective_date: date | None
    article_text: str | None
    source: str = "MOLEG"
    version_status: str = PENDING_MOLEG_API_MAPPING
    raw_payload_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class LawUpdateDetectionResult:
    event: LawUpdateEvent | None
    version: LawArticleVersion | None
    created_event: bool
    impacted_step_codes: list[str]


def detect_law_update(
    db: Session,
    payload: IncomingArticleVersionPayload,
) -> LawUpdateDetectionResult:
    article = db.get(LawArticle, payload.article_id)
    if article is None:
        raise ValueError("law article does not exist")

    same_effective_versions = list(
        db.scalars(
            select(LawArticleVersion)
            .where(
                LawArticleVersion.law_article_id == payload.article_id,
                LawArticleVersion.effective_date == payload.effective_date,
                LawArticleVersion.source == payload.source,
            )
            .order_by(LawArticleVersion.id.asc())
        ).all()
    )
    for version in same_effective_versions:
        if version.article_text == payload.article_text:
            return LawUpdateDetectionResult(
                event=None,
                version=version,
                created_event=False,
                impacted_step_codes=get_impacted_step_codes(db=db, article_id=payload.article_id),
            )

    previous_version = _select_previous_version(db=db, article_id=payload.article_id, effective_date=payload.effective_date)
    change_type = CHANGE_TYPE_CONTENT_CHANGED if same_effective_versions else CHANGE_TYPE_NEW_VERSION
    new_version = LawArticleVersion(
        law_article_id=payload.article_id,
        effective_date=payload.effective_date,
        article_text=payload.article_text,
        raw_payload_json=payload.raw_payload_json,
        source=payload.source,
        version_status=payload.version_status,
    )
    db.add(new_version)
    db.flush()

    event = _get_or_create_event(
        db=db,
        law_id=article.law_id,
        article_id=payload.article_id,
        previous_version_id=None if previous_version is None else previous_version.id,
        new_version_id=new_version.id,
        change_type=change_type,
        effective_date=payload.effective_date,
        source=payload.source,
        metadata_json={"status": "TEST_OR_PENDING_REVIEW"},
    )
    db.commit()
    return LawUpdateDetectionResult(
        event=event,
        version=new_version,
        created_event=True,
        impacted_step_codes=get_impacted_step_codes(db=db, article_id=payload.article_id),
    )


def get_impacted_step_codes(db: Session, article_id: int) -> list[str]:
    step_codes = db.scalars(
        select(ProcedureLegalReference.step_code)
        .where(ProcedureLegalReference.law_article_id == article_id)
        .order_by(ProcedureLegalReference.step_code.asc())
    ).all()
    return sorted(set(step_codes))


def get_law_update_events(db: Session, since: date | None = None) -> list[LawUpdateEvent]:
    statement = select(LawUpdateEvent).order_by(LawUpdateEvent.detected_at.desc(), LawUpdateEvent.id.desc())
    if since is not None:
        statement = statement.where(LawUpdateEvent.detected_at >= since)
    return list(db.scalars(statement).all())


def _select_previous_version(
    db: Session,
    article_id: int,
    effective_date: date | None,
) -> LawArticleVersion | None:
    statement = select(LawArticleVersion).where(LawArticleVersion.law_article_id == article_id)
    if effective_date is not None:
        statement = statement.where(LawArticleVersion.effective_date <= effective_date)
    statement = statement.order_by(LawArticleVersion.effective_date.desc().nullslast(), LawArticleVersion.id.desc())
    return db.scalar(statement)


def _get_or_create_event(
    db: Session,
    law_id: int,
    article_id: int,
    previous_version_id: int | None,
    new_version_id: int,
    change_type: str,
    effective_date: date | None,
    source: str,
    metadata_json: dict[str, Any] | None,
) -> LawUpdateEvent:
    existing = db.scalar(
        select(LawUpdateEvent).where(
            LawUpdateEvent.article_id == article_id,
            LawUpdateEvent.new_version_id == new_version_id,
            LawUpdateEvent.change_type == change_type,
        )
    )
    if existing is not None:
        return existing

    event = LawUpdateEvent(
        law_id=law_id,
        article_id=article_id,
        previous_version_id=previous_version_id,
        new_version_id=new_version_id,
        change_type=change_type,
        effective_date=effective_date,
        status=EVENT_STATUS_PENDING_REVIEW,
        source=source,
        metadata_json=metadata_json,
    )
    db.add(event)
    db.flush()
    return event
