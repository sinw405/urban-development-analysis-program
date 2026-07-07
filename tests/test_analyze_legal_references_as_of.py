from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.services.law_version_service import VERSION_STATUS_CURRENT, VERSION_STATUS_SCHEDULED
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING, TODO_MOLEG_API_ARTICLE_CHECK

client = TestClient(app)

TEST_LAW_NAME = "TEST_LAW_DO_NOT_USE"
TEST_LAW_KEY = "TEST_PHASE6_LAW_KEY_DO_NOT_USE"
TEST_ARTICLE_KEY = "TEST_PHASE6_ARTICLE_KEY_DO_NOT_USE"
TEST_ARTICLE_TEXT = "TEST_ARTICLE_DO_NOT_USE"
TEST_VERSION_CURRENT = "TEST_VERSION_DO_NOT_USE_CURRENT"
TEST_VERSION_SCHEDULED = "TEST_VERSION_DO_NOT_USE_SCHEDULED"
TEST_STEP_CODE = "PROJECT_BASIC_REVIEW"
TEST_SOURCE = "TEST_SOURCE_DO_NOT_USE"


def _delete_test_rows() -> None:
    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_key == TEST_LAW_KEY)).all())
        if not law_ids:
            return
        article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
        db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
        if article_ids:
            db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_article_id.in_(article_ids)))
            db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
            db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
        db.execute(delete(Law).where(Law.id.in_(law_ids)))
        db.commit()
    finally:
        db.close()


def _create_test_reference() -> tuple[int, int]:
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
        db.add_all(
            [
                LawArticleVersion(
                    law_article_id=article.id,
                    effective_date=date(2099, 1, 1),
                    article_text=TEST_VERSION_CURRENT,
                    source=TEST_SOURCE,
                    version_status=PENDING_MOLEG_API_MAPPING,
                    raw_payload_json={"fixture": "TEST_VERSION_CURRENT_DO_NOT_USE"},
                ),
                LawArticleVersion(
                    law_article_id=article.id,
                    effective_date=date(2100, 1, 1),
                    article_text=TEST_VERSION_SCHEDULED,
                    source=TEST_SOURCE,
                    version_status=PENDING_MOLEG_API_MAPPING,
                    raw_payload_json={"fixture": "TEST_VERSION_SCHEDULED_DO_NOT_USE"},
                ),
            ]
        )
        db.add(
            ProcedureLegalReference(
                step_code=TEST_STEP_CODE,
                law_id=law.id,
                law_article_id=article.id,
                reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
                placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
                notes_json={"fixture": "TEST_PROCEDURE_REFERENCE_DO_NOT_USE"},
            )
        )
        db.commit()
        return law.id, article.id
    finally:
        db.close()


def _analyze(as_of: str | None = None) -> dict:
    payload = {
        "project_name": "TEST_PHASE6_ANALYZE_DO_NOT_USE",
        "location": "TEST_LOCATION_DO_NOT_USE",
        "area_square_meters": 100000,
        "implementation_method": "mixed",
        "implementer_type": "public_private_spc",
        "local_government": "TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
    }
    if as_of is not None:
        payload["as_of"] = as_of
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    return response.json()


def test_analyze_returns_as_of_current_and_scheduled_legal_references():
    _delete_test_rows()
    law_id, article_id = _create_test_reference()
    try:
        data = _analyze(as_of="2099-06-15")
        target_step = next(step for step in data["procedures"] if step["step_code"] == TEST_STEP_CODE)
        reference = target_step["legal_references"][0]

        assert data["as_of"] == "2099-06-15"
        assert reference["law_id"] == law_id
        assert reference["law_key"] == TEST_LAW_KEY
        assert reference["article_id"] == article_id
        assert reference["article_key"] == TEST_ARTICLE_KEY
        assert reference["reference_status"] == TODO_MOLEG_API_ARTICLE_CHECK
        assert reference["placeholder"] == TODO_MOLEG_API_ARTICLE_CHECK
        assert reference["current_version"]["temporal_status"] == VERSION_STATUS_CURRENT
        assert reference["current_version"]["effective_date"] == "2099-01-01"
        statuses = {version["effective_date"]: version["temporal_status"] for version in reference["versions"]}
        assert statuses["2099-01-01"] == VERSION_STATUS_CURRENT
        assert statuses["2100-01-01"] == VERSION_STATUS_SCHEDULED
    finally:
        _delete_test_rows()


def test_unconnected_steps_keep_empty_legal_references():
    _delete_test_rows()
    _create_test_reference()
    try:
        data = _analyze(as_of="2099-06-15")
        unconnected_steps = [step for step in data["procedures"] if step["step_code"] != TEST_STEP_CODE]

        assert unconnected_steps
        assert all(step["legal_references"] == [] for step in unconnected_steps)
    finally:
        _delete_test_rows()


def test_analysis_detail_persists_as_of_legal_references_in_result_payload():
    _delete_test_rows()
    _create_test_reference()
    try:
        created = _analyze(as_of="2099-06-15")
        detail_response = client.get(f"/api/analyses/{created['analysis_id']}")

        assert detail_response.status_code == 200
        detail = detail_response.json()
        result_payload = detail["result_payload"]
        target_step = next(step for step in result_payload["procedures"] if step["step_code"] == TEST_STEP_CODE)
        reference = target_step["legal_references"][0]

        assert result_payload["as_of"] == "2099-06-15"
        assert reference["law_key"] == TEST_LAW_KEY
        assert reference["article_key"] == TEST_ARTICLE_KEY
        assert reference["current_version"]["temporal_status"] == VERSION_STATUS_CURRENT
        assert reference["current_version"]["effective_date"] == "2099-01-01"
    finally:
        _delete_test_rows()


def test_analyze_without_as_of_keeps_backward_compatible_shape():
    _delete_test_rows()
    data = _analyze()

    assert data["as_of"] is None
    assert "procedures" in data
    assert "assessments" in data
    assert len(data["procedures"]) > 0
    assert data["procedures"][0]["legal_references"] == []
    for item in data["assessments"]:
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert item["legal_basis"] == TODO_MOLEG_API_ARTICLE_CHECK


def test_phase6_fixtures_do_not_use_real_law_names_article_numbers_or_criteria():
    fixture_values = {
        TEST_LAW_NAME,
        TEST_LAW_KEY,
        TEST_ARTICLE_KEY,
        TEST_ARTICLE_TEXT,
        TEST_VERSION_CURRENT,
        TEST_VERSION_SCHEDULED,
    }

    assert all("TEST_" in value and "DO_NOT_USE" in value for value in fixture_values)
