from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.services.legal_reference_service import (
    PENDING_MOLEG_API_MAPPING,
    TODO_MOLEG_API_ARTICLE_CHECK,
    is_pending_legal_reference_status,
)
from app.services.moleg_adapter import MolegArticleLookupRequest, StubMolegAdapter


client = TestClient(app)
TEST_LAW_NAME = "TEST_LAW_DO_NOT_USE"
TEST_ARTICLE_TEXT = "TEST_ARTICLE_DO_NOT_USE"
TEST_STEP_CODE = "PROJECT_BASIC_REVIEW"


def _delete_test_legal_reference_rows() -> None:
    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_name == TEST_LAW_NAME)).all())
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


def _create_test_procedure_reference() -> None:
    db = SessionLocal()
    try:
        law = Law(
            law_name=TEST_LAW_NAME,
            law_key="TEST_LAW_KEY_DO_NOT_USE",
            source="TEST_SOURCE_DO_NOT_USE",
            mapping_status=PENDING_MOLEG_API_MAPPING,
        )
        db.add(law)
        db.flush()

        article = LawArticle(
            law_id=law.id,
            article_key="TEST_ARTICLE_KEY_DO_NOT_USE",
            article_number_text=TEST_ARTICLE_TEXT,
            article_title="TEST_ARTICLE_TITLE_DO_NOT_USE",
            mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
        )
        db.add(article)
        db.flush()

        version = LawArticleVersion(
            law_article_id=article.id,
            source="TEST_SOURCE_DO_NOT_USE",
            version_status=PENDING_MOLEG_API_MAPPING,
            raw_payload_json={"fixture": "TEST_PAYLOAD_DO_NOT_USE"},
        )
        reference = ProcedureLegalReference(
            step_code=TEST_STEP_CODE,
            law_id=law.id,
            law_article_id=article.id,
            reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
            placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
            notes_json={"fixture": "TEST_REFERENCE_DO_NOT_USE"},
        )
        db.add_all([version, reference])
        db.commit()
    finally:
        db.close()


def test_analyze_keeps_legal_reference_placeholders_empty_and_pending():
    _delete_test_legal_reference_rows()
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "Phase 3 Legal Reference Placeholder Test",
            "location": "Seongnam-si, Gyeonggi-do",
            "area_square_meters": 100000,
            "implementation_method": "mixed",
            "implementer_type": "public_private_spc",
            "local_government": "Seongnam-si",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["procedures"]) > 0
    for step in data["procedures"]:
        assert step["legal_references"] == []
        assert "legal_basis_placeholder" in step
        assert all(is_pending_legal_reference_status(value) for value in step["legal_basis_placeholder"])
        assert not any("Article" in str(reference) for reference in step["legal_references"])
        assert not any("law_article" in str(reference) for reference in step["legal_references"])

    for item in data["assessments"]:
        assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
        assert item["legal_basis"] == TODO_MOLEG_API_ARTICLE_CHECK


def test_analyze_returns_test_only_legal_reference_for_connected_step():
    _delete_test_legal_reference_rows()
    _create_test_procedure_reference()
    try:
        response = client.post(
            "/api/analyze",
            json={
                "project_name": "Phase 3 Legal Reference Connection Test",
                "location": "Seongnam-si, Gyeonggi-do",
                "area_square_meters": 100000,
                "implementation_method": "mixed",
                "implementer_type": "public_private_spc",
                "local_government": "Seongnam-si",
            },
        )

        assert response.status_code == 200
        data = response.json()
        target_step = next(step for step in data["procedures"] if step["step_code"] == TEST_STEP_CODE)

        assert len(target_step["legal_references"]) == 1
        legal_reference = target_step["legal_references"][0]
        assert legal_reference["step_code"] == TEST_STEP_CODE
        assert legal_reference["reference_status"] == TODO_MOLEG_API_ARTICLE_CHECK
        assert legal_reference["placeholder"] == TODO_MOLEG_API_ARTICLE_CHECK
        assert legal_reference["law"]["law_name"] == TEST_LAW_NAME
        assert legal_reference["law"]["mapping_status"] == PENDING_MOLEG_API_MAPPING
        assert legal_reference["law_article"]["article_number_text"] == TEST_ARTICLE_TEXT
        assert legal_reference["law_article"]["mapping_status"] == TODO_MOLEG_API_ARTICLE_CHECK
        assert all("TEST_" in str(legal_reference[key]) or legal_reference[key] == TODO_MOLEG_API_ARTICLE_CHECK for key in ["law", "law_article", "placeholder"])

        for item in data["assessments"]:
            assert item["threshold"] == "TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA"
            assert item["legal_basis"] == TODO_MOLEG_API_ARTICLE_CHECK
    finally:
        _delete_test_legal_reference_rows()


def test_moleg_stub_returns_pending_without_network_call():
    adapter = StubMolegAdapter()
    result = adapter.lookup_article(MolegArticleLookupRequest(law_name=TEST_LAW_NAME))

    assert result.mapping_status == PENDING_MOLEG_API_MAPPING
    assert result.raw_payload is None
