from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.services.law_version_service import (
    VERSION_STATUS_CURRENT,
    VERSION_STATUS_PREVIOUS,
    VERSION_STATUS_SCHEDULED,
    get_article_versions,
    get_current_article_version,
)
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING, TODO_MOLEG_API_ARTICLE_CHECK

client = TestClient(app)

TEST_LAW_NAME = "TEST_LAW_DO_NOT_USE"
TEST_LAW_KEY = "TEST_PHASE5_LAW_KEY_DO_NOT_USE"
TEST_ARTICLE_KEY = "TEST_PHASE5_ARTICLE_KEY_DO_NOT_USE"
TEST_ARTICLE_TEXT = "TEST_ARTICLE_DO_NOT_USE"
TEST_VERSION_PREVIOUS = "TEST_VERSION_DO_NOT_USE_PREVIOUS"
TEST_VERSION_CURRENT = "TEST_VERSION_DO_NOT_USE_CURRENT"
TEST_VERSION_SCHEDULED = "TEST_VERSION_DO_NOT_USE_SCHEDULED"
TEST_SOURCE = "TEST_SOURCE_DO_NOT_USE"


def _delete_test_laws() -> None:
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


def _create_version_fixture() -> tuple[int, int]:
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
                    article_text=TEST_VERSION_PREVIOUS,
                    source=TEST_SOURCE,
                    version_status=PENDING_MOLEG_API_MAPPING,
                    raw_payload_json={"fixture": "TEST_VERSION_PREVIOUS_DO_NOT_USE"},
                ),
                LawArticleVersion(
                    law_article_id=article.id,
                    effective_date=date(2099, 6, 1),
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
        db.commit()
        return law.id, article.id
    finally:
        db.close()


def test_as_of_selects_current_previous_and_scheduled_versions():
    _delete_test_laws()
    law_id, article_id = _create_version_fixture()
    db = SessionLocal()
    try:
        classified = get_article_versions(db=db, article_id=article_id, as_of=date(2099, 6, 15))
        by_text = {item.version.article_text: item.temporal_status for item in classified}
        current = get_current_article_version(db=db, article_id=article_id, as_of=date(2099, 6, 15))

        assert law_id > 0
        assert by_text[TEST_VERSION_PREVIOUS] == VERSION_STATUS_PREVIOUS
        assert by_text[TEST_VERSION_CURRENT] == VERSION_STATUS_CURRENT
        assert by_text[TEST_VERSION_SCHEDULED] == VERSION_STATUS_SCHEDULED
        assert current is not None
        assert current.article_text == TEST_VERSION_CURRENT
    finally:
        db.close()
        _delete_test_laws()


def test_law_articles_api_returns_current_version_for_as_of():
    _delete_test_laws()
    law_id, article_id = _create_version_fixture()
    try:
        response = client.get(f"/api/laws/{law_id}/articles?as_of=2099-06-15")

        assert response.status_code == 200
        data = response.json()
        assert data["as_of"] == "2099-06-15"
        assert len(data["items"]) == 1
        article = data["items"][0]
        assert article["id"] == article_id
        assert article["article_number_text"] == TEST_ARTICLE_TEXT
        assert article["current_version"]["article_text"] == TEST_VERSION_CURRENT
        assert article["current_version"]["temporal_status"] == VERSION_STATUS_CURRENT
    finally:
        _delete_test_laws()


def test_law_article_versions_api_returns_temporal_statuses():
    _delete_test_laws()
    law_id, article_id = _create_version_fixture()
    try:
        response = client.get(f"/api/laws/{law_id}/articles/{article_id}/versions?as_of=2099-06-15")

        assert response.status_code == 200
        data = response.json()
        by_text = {item["article_text"]: item["temporal_status"] for item in data["items"]}
        assert data["current_version"]["article_text"] == TEST_VERSION_CURRENT
        assert by_text[TEST_VERSION_PREVIOUS] == VERSION_STATUS_PREVIOUS
        assert by_text[TEST_VERSION_CURRENT] == VERSION_STATUS_CURRENT
        assert by_text[TEST_VERSION_SCHEDULED] == VERSION_STATUS_SCHEDULED
    finally:
        _delete_test_laws()


def test_existing_analyze_response_shape_keeps_phase5_compatibility():
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "TEST_PHASE5_ANALYZE_DO_NOT_USE",
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
    assert "analysis_id" in data
    assert "project_id" in data
    assert len(data["procedures"]) > 0
    assert "legal_references" in data["procedures"][0]
    assert data["procedures"][0]["legal_references"] == []
    for item in data["assessments"]:
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert item["legal_basis"] == TODO_MOLEG_API_ARTICLE_CHECK


def test_phase5_fixtures_do_not_use_real_law_names_or_article_numbers():
    fixture_values = {
        TEST_LAW_NAME,
        TEST_LAW_KEY,
        TEST_ARTICLE_KEY,
        TEST_ARTICLE_TEXT,
        TEST_VERSION_PREVIOUS,
        TEST_VERSION_CURRENT,
        TEST_VERSION_SCHEDULED,
    }

    assert all("TEST_" in value and "DO_NOT_USE" in value for value in fixture_values)
