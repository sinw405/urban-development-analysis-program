from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Law, LawArticle, LawArticleVersion, LawUpdateEvent, ProcedureLegalReference
from app.services.law_update_service import CHANGE_TYPE_NEW_VERSION, EVENT_STATUS_PENDING_REVIEW
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING, TODO_MOLEG_API_ARTICLE_CHECK

TEST_LAW_NAME = "TEST_LAW_DO_NOT_USE"
TEST_LAW_KEY = "TEST_DEMO_LAW_KEY_DO_NOT_USE"
TEST_ARTICLE_KEY = "TEST_DEMO_ARTICLE_KEY_DO_NOT_USE"
TEST_ARTICLE_TEXT = "TEST_ARTICLE_DO_NOT_USE"
TEST_VERSION_CURRENT = "TEST_VERSION_DO_NOT_USE_CURRENT"
TEST_VERSION_SCHEDULED = "TEST_VERSION_DO_NOT_USE_SCHEDULED"
TEST_PROJECT_NAME = "TEST_PROJECT_DO_NOT_USE"
TEST_PROCEDURE_STEP_CODE = "PROJECT_BASIC_REVIEW"
TEST_SOURCE = "TEST_SOURCE_DO_NOT_USE"
CURRENT_EFFECTIVE_DATE = date(2099, 1, 1)
SCHEDULED_EFFECTIVE_DATE = date(2100, 1, 1)

TEST_CORE_PROCEDURE_STEP_CODES = (
    "PROJECT_BASIC_REVIEW",
    "ZONE_DESIGNATION_REVIEW",
    "RESIDENT_OPINION_HEARING",
    "RELATED_AGENCY_CONSULTATION",
    "URBAN_PLANNING_COMMITTEE_REVIEW",
    "ZONE_DESIGNATION_NOTIFICATION",
    "DEVELOPMENT_PLAN_ESTABLISHMENT",
    "IMPLEMENTER_DESIGNATION_REVIEW",
    "IMPLEMENTATION_PLAN_AUTHORIZATION",
    "PROJECT_IMPLEMENTATION",
    "COMPLETION_INSPECTION",
)


def seed_demo_data(db: Session) -> dict[str, Any]:
    law = _get_or_create_law(db)
    article = _get_or_create_article(db, law_id=law.id, step_code=TEST_PROCEDURE_STEP_CODE)
    current_version = _get_or_create_version(
        db=db,
        article_id=article.id,
        effective_date=CURRENT_EFFECTIVE_DATE,
        article_text=TEST_VERSION_CURRENT,
    )
    scheduled_version = _get_or_create_version(
        db=db,
        article_id=article.id,
        effective_date=SCHEDULED_EFFECTIVE_DATE,
        article_text=TEST_VERSION_SCHEDULED,
    )

    references = []
    for step_code in TEST_CORE_PROCEDURE_STEP_CODES:
        step_article = article if step_code == TEST_PROCEDURE_STEP_CODE else _get_or_create_article(
            db=db,
            law_id=law.id,
            step_code=step_code,
        )
        if step_code != TEST_PROCEDURE_STEP_CODE:
            _get_or_create_version(
                db=db,
                article_id=step_article.id,
                effective_date=CURRENT_EFFECTIVE_DATE,
                article_text=f"TEST_VERSION_DO_NOT_USE_CURRENT_{step_code}",
            )
            _get_or_create_version(
                db=db,
                article_id=step_article.id,
                effective_date=SCHEDULED_EFFECTIVE_DATE,
                article_text=f"TEST_VERSION_DO_NOT_USE_SCHEDULED_{step_code}",
            )
        references.append(_get_or_create_procedure_reference(db=db, law_id=law.id, article_id=step_article.id, step_code=step_code))

    event = _get_or_create_update_event(
        db=db,
        law_id=law.id,
        article_id=article.id,
        previous_version_id=current_version.id,
        new_version_id=scheduled_version.id,
    )
    db.commit()
    return {
        "law_id": law.id,
        "article_id": article.id,
        "current_version_id": current_version.id,
        "scheduled_version_id": scheduled_version.id,
        "procedure_legal_reference_id": references[0].id,
        "procedure_legal_reference_ids": [reference.id for reference in references],
        "law_update_event_id": event.id,
        "test_project_name": TEST_PROJECT_NAME,
        "test_step_code": TEST_PROCEDURE_STEP_CODE,
        "test_core_step_codes": list(TEST_CORE_PROCEDURE_STEP_CODES),
    }


def _get_or_create_law(db: Session) -> Law:
    law = db.scalar(select(Law).where(Law.law_key == TEST_LAW_KEY))
    if law is None:
        law = Law(
            law_name=TEST_LAW_NAME,
            law_key=TEST_LAW_KEY,
            source=TEST_SOURCE,
            mapping_status=PENDING_MOLEG_API_MAPPING,
        )
        db.add(law)
        db.flush()
    return law


def _article_key_for_step(step_code: str) -> str:
    if step_code == TEST_PROCEDURE_STEP_CODE:
        return TEST_ARTICLE_KEY
    return f"TEST_DEMO_ARTICLE_KEY_{step_code}_DO_NOT_USE"


def _get_or_create_article(db: Session, law_id: int, step_code: str) -> LawArticle:
    article_key = _article_key_for_step(step_code)
    article = db.scalar(
        select(LawArticle).where(
            LawArticle.law_id == law_id,
            LawArticle.article_key == article_key,
        )
    )
    if article is None:
        article = LawArticle(
            law_id=law_id,
            article_key=article_key,
            article_number_text=TEST_ARTICLE_TEXT,
            article_title=f"TEST_ARTICLE_TITLE_{step_code}_DO_NOT_USE",
            mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
        )
        db.add(article)
        db.flush()
    return article


def _get_or_create_version(db: Session, article_id: int, effective_date: date, article_text: str) -> LawArticleVersion:
    version = db.scalar(
        select(LawArticleVersion).where(
            LawArticleVersion.law_article_id == article_id,
            LawArticleVersion.effective_date == effective_date,
            LawArticleVersion.source == TEST_SOURCE,
            LawArticleVersion.article_text == article_text,
        )
    )
    if version is None:
        version = LawArticleVersion(
            law_article_id=article_id,
            effective_date=effective_date,
            article_text=article_text,
            raw_payload_json={"fixture": article_text},
            source=TEST_SOURCE,
            version_status=PENDING_MOLEG_API_MAPPING,
        )
        db.add(version)
        db.flush()
    return version


def _get_or_create_procedure_reference(db: Session, law_id: int, article_id: int, step_code: str) -> ProcedureLegalReference:
    reference = db.scalar(
        select(ProcedureLegalReference).where(
            ProcedureLegalReference.step_code == step_code,
            ProcedureLegalReference.law_article_id == article_id,
        )
    )
    if reference is None:
        reference = ProcedureLegalReference(
            step_code=step_code,
            law_id=law_id,
            law_article_id=article_id,
            reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
            placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
            notes_json={
                "fixture": "TEST_DEMO_REFERENCE_DO_NOT_USE",
                "verification_status": "검증 필요",
                "coverage_role": "core_procedure_candidate",
            },
        )
        db.add(reference)
        db.flush()
    return reference


def _get_or_create_update_event(
    db: Session,
    law_id: int,
    article_id: int,
    previous_version_id: int,
    new_version_id: int,
) -> LawUpdateEvent:
    event = db.scalar(
        select(LawUpdateEvent).where(
            LawUpdateEvent.article_id == article_id,
            LawUpdateEvent.new_version_id == new_version_id,
            LawUpdateEvent.change_type == CHANGE_TYPE_NEW_VERSION,
        )
    )
    if event is None:
        event = LawUpdateEvent(
            law_id=law_id,
            article_id=article_id,
            previous_version_id=previous_version_id,
            new_version_id=new_version_id,
            change_type=CHANGE_TYPE_NEW_VERSION,
            effective_date=SCHEDULED_EFFECTIVE_DATE,
            status=EVENT_STATUS_PENDING_REVIEW,
            source=TEST_SOURCE,
            metadata_json={"fixture": "TEST_DEMO_UPDATE_EVENT_DO_NOT_USE"},
        )
        db.add(event)
        db.flush()
    return event
