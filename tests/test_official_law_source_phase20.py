from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.schemas.official_law_source import MATCH_STATUS_MATCHED, MATCH_STATUS_PARTIAL, MATCH_STATUS_UNMATCHED
from app.services.legal_reference_service import TODO_MOLEG_API_ARTICLE_CHECK
from app.services.legal_reference_verification_service import verify_candidate_reference
from app.services.official_law_source import MockOfficialLawSourceProvider


client = TestClient(app)


def _reference(
    article_number_text: str = "TEST_ARTICLE_DO_NOT_USE",
    article_title: str = "TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
) -> ProcedureLegalReference:
    law = Law(
        id=990001,
        law_name="TEST_LAW_DO_NOT_USE",
        law_key="TEST_PHASE20_LAW_KEY_DO_NOT_USE",
        source="TEST_SOURCE_DO_NOT_USE",
        mapping_status="PENDING_MOLEG_API_MAPPING",
    )
    article = LawArticle(
        id=990002,
        law_id=law.id,
        article_key="TEST_PHASE20_ARTICLE_KEY_DO_NOT_USE",
        article_number_text=article_number_text,
        article_title=article_title,
        mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
    )
    return ProcedureLegalReference(
        id=990003,
        step_code="PROJECT_BASIC_REVIEW",
        law=law,
        law_article=article,
        reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
        placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
        notes_json={"reference_quality": "candidate"},
    )


def _delete_phase20_rows() -> None:
    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_key == "TEST_PHASE20_LAW_KEY_DO_NOT_USE")).all())
        if not law_ids:
            return
        article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
        db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
        if article_ids:
            db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
            db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_article_id.in_(article_ids)))
            db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
        db.execute(delete(Law).where(Law.id.in_(law_ids)))
        db.commit()
    finally:
        db.close()


def _create_phase20_reference() -> int:
    db = SessionLocal()
    try:
        law = Law(
            law_name="TEST_LAW_DO_NOT_USE",
            law_key="TEST_PHASE20_LAW_KEY_DO_NOT_USE",
            source="TEST_SOURCE_DO_NOT_USE",
            mapping_status="PENDING_MOLEG_API_MAPPING",
        )
        db.add(law)
        db.flush()

        article = LawArticle(
            law_id=law.id,
            article_key="TEST_PHASE20_ARTICLE_KEY_DO_NOT_USE",
            article_number_text="TEST_ARTICLE_DO_NOT_USE",
            article_title="TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
            mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
        )
        db.add(article)
        db.flush()

        reference = ProcedureLegalReference(
            step_code="PROJECT_BASIC_REVIEW",
            law_id=law.id,
            law_article_id=article.id,
            reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
            placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
            notes_json={"reference_quality": "candidate", "fixture": "TEST_PHASE20_DO_NOT_USE"},
        )
        db.add(reference)
        db.commit()
        return reference.id
    finally:
        db.close()


def test_mock_official_law_source_provider_returns_article():
    provider = MockOfficialLawSourceProvider()

    article = provider.get_article_by_law_and_article("TEST_LAW_DO_NOT_USE", "TEST_ARTICLE_DO_NOT_USE")

    assert article is not None
    assert article.law_name == "TEST_LAW_DO_NOT_USE"
    assert article.article_number_text == "TEST_ARTICLE_DO_NOT_USE"
    assert article.article_title == "TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE"
    assert article.article_text == "TEST_VERSION_DO_NOT_USE_CURRENT"
    assert article.source_url.startswith("https://mock.official.local/")
    assert article.source_type == "mock_official"


def test_candidate_reference_matches_mock_official_source():
    result = verify_candidate_reference(_reference())

    assert result.match_status == MATCH_STATUS_MATCHED
    assert result.can_promote_to_verified is True
    assert result.official_source_snapshot is not None
    assert result.official_source_snapshot.source_type == "mock_official"


def test_candidate_reference_with_different_article_number_is_unmatched():
    result = verify_candidate_reference(_reference(article_number_text="TEST_UNKNOWN_ARTICLE_DO_NOT_USE"))

    assert result.match_status == MATCH_STATUS_UNMATCHED
    assert result.can_promote_to_verified is False
    assert result.official_source_snapshot is None


def test_candidate_reference_with_partial_information_is_partial():
    result = verify_candidate_reference(
        _reference(
            article_number_text="TEST_PARTIAL_ARTICLE_DO_NOT_USE",
            article_title="ALPHA BETA",
        )
    )

    assert result.match_status == MATCH_STATUS_PARTIAL
    assert result.can_promote_to_verified is False
    assert result.official_source_snapshot is not None


def test_verify_preview_api_returns_promotion_preview_without_promoting_seed_data():
    _delete_phase20_rows()
    reference_id = _create_phase20_reference()
    try:
        response = client.post(
            "/api/legal-references/verify-preview",
            json={"procedure_reference_ids": [reference_id]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["procedure_reference_id"] == reference_id
        assert item["match_status"] == MATCH_STATUS_MATCHED
        assert item["can_promote_to_verified"] is True
        assert item["candidate_reference"]["reference_quality"] == "candidate"
        assert item["official_source_snapshot"]["source_type"] == "mock_official"

        db = SessionLocal()
        try:
            stored = db.get(ProcedureLegalReference, reference_id)
            assert stored is not None
            assert stored.reference_status == TODO_MOLEG_API_ARTICLE_CHECK
            assert stored.notes_json["reference_quality"] == "candidate"
        finally:
            db.close()
    finally:
        _delete_phase20_rows()
