from sqlalchemy import delete, func, select
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, LawUpdateEvent, ProcedureLegalReference
from app.services.dev_seed_service import (
    TEST_LAW_KEY,
    TEST_LAW_NAME,
    TEST_ARTICLE_KEY,
    TEST_ARTICLE_TEXT,
    TEST_PROJECT_NAME,
    TEST_PROCEDURE_STEP_CODE,
    TEST_VERSION_CURRENT,
    TEST_VERSION_SCHEDULED,
    seed_demo_data,
)
from app.services.legal_reference_service import TODO_MOLEG_API_ARTICLE_CHECK

client = TestClient(app)


def _delete_demo_seed_rows() -> None:
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


def test_demo_seed_is_idempotent_and_creates_expected_test_rows():
    _delete_demo_seed_rows()
    db = SessionLocal()
    try:
        first = seed_demo_data(db)
        second = seed_demo_data(db)

        assert first == second
        assert first["test_project_name"] == TEST_PROJECT_NAME
        assert first["test_step_code"] == TEST_PROCEDURE_STEP_CODE
        assert db.scalar(select(func.count()).select_from(Law).where(Law.law_key == TEST_LAW_KEY)) == 1
        assert db.scalar(select(func.count()).select_from(LawArticle).where(LawArticle.article_key == TEST_ARTICLE_KEY)) == 1
        assert db.scalar(select(func.count()).select_from(LawUpdateEvent).where(LawUpdateEvent.law_id == first["law_id"])) == 1
        assert db.scalar(
            select(func.count()).select_from(LawArticleVersion).where(
                LawArticleVersion.law_article_id == first["article_id"]
            )
        ) == 2
    finally:
        db.close()
        _delete_demo_seed_rows()


def test_demo_seed_legal_reference_is_visible_in_analyze_response():
    _delete_demo_seed_rows()
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()

    try:
        response = client.post(
            "/api/analyze",
            json={
                "project_name": TEST_PROJECT_NAME,
                "location": "TEST_LOCATION_DO_NOT_USE",
                "area_square_meters": 100000,
                "implementation_method": "mixed",
                "implementer_type": "public_private_spc",
                "local_government": "TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
                "as_of": "2099-06-15",
            },
        )
        assert response.status_code == 200
        data = response.json()
        target_step = next(step for step in data["procedures"] if step["step_code"] == TEST_PROCEDURE_STEP_CODE)
        reference = target_step["legal_references"][0]

        assert reference["law_key"] == TEST_LAW_KEY
        assert reference["article_key"] == TEST_ARTICLE_KEY
        assert reference["current_version"]["temporal_status"] == "current"
        assert any(version["temporal_status"] == "scheduled" for version in reference["versions"])
        assert "law_name" not in reference
        assert "article_number_text" not in reference
    finally:
        _delete_demo_seed_rows()


def test_demo_seed_law_update_event_is_visible_in_api():
    _delete_demo_seed_rows()
    db = SessionLocal()
    try:
        seeded = seed_demo_data(db)
    finally:
        db.close()

    try:
        response = client.get("/api/law-updates")
        assert response.status_code == 200
        items = response.json()["items"]
        event = next(item for item in items if item["event_id"] == seeded["law_update_event_id"])

        assert event["law_id"] == seeded["law_id"]
        assert event["article_id"] == seeded["article_id"]
        assert event["impacted_step_codes"] == [TEST_PROCEDURE_STEP_CODE]
        assert event["status"]
    finally:
        _delete_demo_seed_rows()


def test_demo_seed_keeps_existing_analyze_shape_and_placeholders():
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "TEST_PHASE9_COMPAT_DO_NOT_USE",
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
    assert data["procedures"][0]["legal_references"] == []
    for item in data["assessments"]:
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert item["legal_basis"] == TODO_MOLEG_API_ARTICLE_CHECK


def test_demo_seed_uses_test_only_names():
    values = {
        TEST_LAW_NAME,
        TEST_LAW_KEY,
        TEST_ARTICLE_KEY,
        TEST_ARTICLE_TEXT,
        TEST_PROJECT_NAME,
        TEST_VERSION_CURRENT,
        TEST_VERSION_SCHEDULED,
    }

    assert all("TEST_" in value and "DO_NOT_USE" in value for value in values)
    assert TEST_PROCEDURE_STEP_CODE == "PROJECT_BASIC_REVIEW"
