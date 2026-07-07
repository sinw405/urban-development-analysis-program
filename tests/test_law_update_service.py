from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, LawUpdateEvent, ProcedureLegalReference
from app.services.law_update_service import (
    CHANGE_TYPE_NEW_VERSION,
    IncomingArticleVersionPayload,
    detect_law_update,
    get_impacted_step_codes,
)
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING, TODO_MOLEG_API_ARTICLE_CHECK

client = TestClient(app)

TEST_LAW_NAME = "TEST_LAW_DO_NOT_USE"
TEST_LAW_KEY = "TEST_PHASE7_LAW_KEY_DO_NOT_USE"
TEST_ARTICLE_KEY = "TEST_PHASE7_ARTICLE_KEY_DO_NOT_USE"
TEST_ARTICLE_TEXT = "TEST_ARTICLE_DO_NOT_USE"
TEST_VERSION_EXISTING = "TEST_VERSION_DO_NOT_USE_EXISTING"
TEST_VERSION_NEW = "TEST_VERSION_DO_NOT_USE_NEW"
TEST_STEP_CODE = "TEST_PROCEDURE_STEP_CODE_DO_NOT_USE"
TEST_SOURCE = "TEST_SOURCE_DO_NOT_USE"


def _delete_test_rows() -> None:
    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_key == TEST_LAW_KEY)).all())
        if not law_ids:
            return
        article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
        db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
        db.execute(delete(LawUpdateEvent).where(LawUpdateEvent.law_id.in_(law_ids)))
        if article_ids:
            db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_article_id.in_(article_ids)))
            db.execute(delete(LawUpdateEvent).where(LawUpdateEvent.article_id.in_(article_ids)))
            db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
            db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
        db.execute(delete(Law).where(Law.id.in_(law_ids)))
        db.commit()
    finally:
        db.close()


def _create_article_fixture(connect_step: bool = True) -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        law = Law(
            law_name=TEST_LAW_NAME,
            law_key=TEST_LAW_KEY,
            source=TEST_SOURCE,
            mapping_status=PENDING_MOLEG_API_MAPPING,
        )
        db.add(law)
        db.flush()
        article = LawArticle(
            law_id=law.id,
            article_key=TEST_ARTICLE_KEY,
            article_number_text=TEST_ARTICLE_TEXT,
            article_title="TEST_ARTICLE_TITLE_DO_NOT_USE",
            mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
        )
        db.add(article)
        db.flush()
        version = LawArticleVersion(
            law_article_id=article.id,
            effective_date=date(2099, 1, 1),
            article_text=TEST_VERSION_EXISTING,
            source=TEST_SOURCE,
            version_status=PENDING_MOLEG_API_MAPPING,
            raw_payload_json={"fixture": "TEST_VERSION_EXISTING_DO_NOT_USE"},
        )
        db.add(version)
        db.flush()
        if connect_step:
            db.add(
                ProcedureLegalReference(
                    step_code=TEST_STEP_CODE,
                    law_id=law.id,
                    law_article_id=article.id,
                    reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
                    placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
                    notes_json={"fixture": "TEST_REFERENCE_DO_NOT_USE"},
                )
            )
        db.commit()
        return law.id, article.id, version.id
    finally:
        db.close()


def _incoming_payload(article_id: int) -> IncomingArticleVersionPayload:
    return IncomingArticleVersionPayload(
        article_id=article_id,
        effective_date=date(2100, 1, 1),
        article_text=TEST_VERSION_NEW,
        source=TEST_SOURCE,
        version_status=PENDING_MOLEG_API_MAPPING,
        raw_payload_json={"fixture": "TEST_VERSION_NEW_DO_NOT_USE"},
    )


def test_new_fake_version_creates_update_event_and_impacted_step_codes():
    _delete_test_rows()
    law_id, article_id, previous_version_id = _create_article_fixture(connect_step=True)
    db = SessionLocal()
    try:
        result = detect_law_update(db=db, payload=_incoming_payload(article_id=article_id))

        assert result.created_event is True
        assert result.event is not None
        assert result.event.law_id == law_id
        assert result.event.article_id == article_id
        assert result.event.previous_version_id == previous_version_id
        assert result.event.new_version_id == result.version.id
        assert result.event.change_type == CHANGE_TYPE_NEW_VERSION
        assert result.event.effective_date == date(2100, 1, 1)
        assert result.impacted_step_codes == [TEST_STEP_CODE]
    finally:
        db.close()
        _delete_test_rows()


def test_same_fake_payload_does_not_create_duplicate_event():
    _delete_test_rows()
    _law_id, article_id, _previous_version_id = _create_article_fixture(connect_step=True)
    db = SessionLocal()
    try:
        first = detect_law_update(db=db, payload=_incoming_payload(article_id=article_id))
        second = detect_law_update(db=db, payload=_incoming_payload(article_id=article_id))
        event_count = db.scalar(select(func.count()).select_from(LawUpdateEvent).where(LawUpdateEvent.article_id == article_id))

        assert first.created_event is True
        assert second.created_event is False
        assert second.event is None
        assert second.version.id == first.version.id
        assert event_count == 1
    finally:
        db.close()
        _delete_test_rows()


def test_unconnected_article_returns_empty_impacted_step_codes():
    _delete_test_rows()
    _law_id, article_id, _previous_version_id = _create_article_fixture(connect_step=False)
    db = SessionLocal()
    try:
        result = detect_law_update(db=db, payload=_incoming_payload(article_id=article_id))

        assert result.created_event is True
        assert result.impacted_step_codes == []
        assert get_impacted_step_codes(db=db, article_id=article_id) == []
    finally:
        db.close()
        _delete_test_rows()


def test_law_update_api_lists_events_and_since_filter():
    _delete_test_rows()
    _law_id, article_id, _previous_version_id = _create_article_fixture(connect_step=True)
    db = SessionLocal()
    try:
        created = detect_law_update(db=db, payload=_incoming_payload(article_id=article_id))
        event_id = created.event.id
    finally:
        db.close()

    try:
        list_response = client.get("/api/law-updates")
        assert list_response.status_code == 200
        items = list_response.json()["items"]
        assert any(item["event_id"] == event_id and item["impacted_step_codes"] == [TEST_STEP_CODE] for item in items)

        since_response = client.get("/api/law-updates?since=2000-01-01")
        assert since_response.status_code == 200
        assert any(item["event_id"] == event_id for item in since_response.json()["items"])

        future_response = client.get("/api/law-updates?since=2200-01-01")
        assert future_response.status_code == 200
        assert not any(item["event_id"] == event_id for item in future_response.json()["items"])

        detail_response = client.get(f"/api/law-updates/{event_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["event_id"] == event_id
        assert detail["change_type"] == CHANGE_TYPE_NEW_VERSION
        assert detail["impacted_step_codes"] == [TEST_STEP_CODE]
    finally:
        _delete_test_rows()


def test_existing_analyze_response_still_works_after_law_update_events():
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "TEST_PHASE7_ANALYZE_DO_NOT_USE",
            "location": "TEST_LOCATION_DO_NOT_USE",
            "area_square_meters": 100000,
            "implementation_method": "mixed",
            "implementer_type": "public_private_spc",
            "local_government": "TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "procedures" in data
    assert "assessments" in data
    assert len(data["procedures"]) > 0
    assert data["procedures"][0]["legal_references"] == []
    for item in data["assessments"]:
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert item["legal_basis"] == TODO_MOLEG_API_ARTICLE_CHECK


def test_phase7_fixtures_do_not_use_real_law_names_article_numbers_or_criteria():
    fixture_values = {
        TEST_LAW_NAME,
        TEST_LAW_KEY,
        TEST_ARTICLE_KEY,
        TEST_ARTICLE_TEXT,
        TEST_VERSION_EXISTING,
        TEST_VERSION_NEW,
        TEST_STEP_CODE,
    }

    assert all("TEST_" in value and "DO_NOT_USE" in value for value in fixture_values)
