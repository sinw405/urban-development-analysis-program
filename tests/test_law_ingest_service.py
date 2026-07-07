from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.services.law_ingest_service import LawIngestService
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING, TODO_MOLEG_API_ARTICLE_CHECK

client = TestClient(app)

TEST_LAW_NAME = "TEST_LAW_DO_NOT_USE"
TEST_LAW_KEY = "TEST_LAW_KEY_DO_NOT_USE"
TEST_ARTICLE_KEY = "TEST_ARTICLE_KEY_DO_NOT_USE"
TEST_ARTICLE_TEXT = "TEST_ARTICLE_DO_NOT_USE"
TEST_VERSION_TEXT = "TEST_VERSION_DO_NOT_USE"
TEST_EFFECTIVE_DATE = "2099-01-01"


def _fake_law_detail_payload() -> dict:
    return {
        "law_name": TEST_LAW_NAME,
        "law_key": TEST_LAW_KEY,
        "source": "TEST_SOURCE_DO_NOT_USE",
        "mapping_status": PENDING_MOLEG_API_MAPPING,
        "articles": [
            {
                "article_key": TEST_ARTICLE_KEY,
                "article_number_text": TEST_ARTICLE_TEXT,
                "article_title": "TEST_ARTICLE_TITLE_DO_NOT_USE",
                "mapping_status": TODO_MOLEG_API_ARTICLE_CHECK,
                "versions": [
                    {
                        "effective_date": TEST_EFFECTIVE_DATE,
                        "article_text": TEST_VERSION_TEXT,
                        "source": "TEST_SOURCE_DO_NOT_USE",
                        "version_status": PENDING_MOLEG_API_MAPPING,
                    }
                ],
            }
        ],
    }


def _delete_test_laws() -> None:
    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_name == TEST_LAW_NAME)).all())
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


def test_fake_moleg_payload_is_saved_to_law_article_version_tables():
    _delete_test_laws()
    db = SessionLocal()
    try:
        result = LawIngestService().ingest_law_detail_payload(db=db, payload=_fake_law_detail_payload())

        law = db.get(Law, result.law_id)
        article = db.get(LawArticle, result.article_ids[0])
        version = db.get(LawArticleVersion, result.version_ids[0])

        assert result.created_law is True
        assert law is not None
        assert law.law_name == TEST_LAW_NAME
        assert law.law_key == TEST_LAW_KEY
        assert law.mapping_status == PENDING_MOLEG_API_MAPPING
        assert article is not None
        assert article.article_key == TEST_ARTICLE_KEY
        assert article.article_number_text == TEST_ARTICLE_TEXT
        assert article.mapping_status == TODO_MOLEG_API_ARTICLE_CHECK
        assert version is not None
        assert version.effective_date == date.fromisoformat(TEST_EFFECTIVE_DATE)
        assert version.article_text == TEST_VERSION_TEXT
        assert version.version_status == PENDING_MOLEG_API_MAPPING
    finally:
        db.close()
        _delete_test_laws()


def test_fake_moleg_payload_upsert_prevents_duplicate_law_article_version_rows():
    _delete_test_laws()
    db = SessionLocal()
    try:
        service = LawIngestService()
        first = service.ingest_law_detail_payload(db=db, payload=_fake_law_detail_payload())
        second = service.ingest_law_detail_payload(db=db, payload=_fake_law_detail_payload())

        assert first.law_id == second.law_id
        assert first.article_ids == second.article_ids
        assert first.version_ids == second.version_ids
        assert second.created_law is False

        law_count = db.scalar(select(func.count()).select_from(Law).where(Law.law_name == TEST_LAW_NAME))
        article_count = db.scalar(select(func.count()).select_from(LawArticle).where(LawArticle.law_id == first.law_id))
        version_count = db.scalar(
            select(func.count()).select_from(LawArticleVersion).where(
                LawArticleVersion.law_article_id == first.article_ids[0]
            )
        )

        assert law_count == 1
        assert article_count == 1
        assert version_count == 1
    finally:
        db.close()
        _delete_test_laws()


def test_laws_internal_api_lists_test_only_ingested_law_and_articles():
    _delete_test_laws()
    db = SessionLocal()
    try:
        result = LawIngestService().ingest_law_detail_payload(db=db, payload=_fake_law_detail_payload())
    finally:
        db.close()

    try:
        laws_response = client.get("/api/laws")
        assert laws_response.status_code == 200
        law_items = laws_response.json()["items"]
        assert any(item["id"] == result.law_id and item["law_name"] == TEST_LAW_NAME for item in law_items)

        articles_response = client.get(f"/api/laws/{result.law_id}/articles")
        assert articles_response.status_code == 200
        article_items = articles_response.json()["items"]
        assert len(article_items) == 1
        assert article_items[0]["article_number_text"] == TEST_ARTICLE_TEXT
        assert article_items[0]["mapping_status"] == TODO_MOLEG_API_ARTICLE_CHECK
    finally:
        _delete_test_laws()
