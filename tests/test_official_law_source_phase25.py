from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import (
    Law,
    LawArticle,
    LawArticleVersion,
    OfficialLawArticleRecord,
    OfficialLawDocument,
    OfficialLawIngestRun,
    OfficialLawSourceEvidence,
    ProcedureLegalReference,
)
from app.services.legal_reference_service import TODO_MOLEG_API_ARTICLE_CHECK
from app.services.official_law_persistence_service import ingest_fixture_document
from app.services.official_law_source import MolegOpenApiLawSourceProvider

client = TestClient(app)
SECRET = "TEST_PHASE25_SECRET_DO_NOT_USE"
URBAN = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
ARTICLE_3 = "\uc81c3\uc870"
LAW_KEY = "TEST_PHASE25_LAW_KEY_DO_NOT_USE"
ARTICLE_KEY = "TEST_PHASE25_ARTICLE_KEY_DO_NOT_USE"
STEP_CODE = "PROJECT_BASIC_REVIEW"
MST = "259999"
LAW_ID = "250099"

SEARCH_FIXTURE = {
    "LawSearch": {
        "law": [
            {
                "\ubc95\ub839\uba85\ud55c\uae00": URBAN,
                "\ubc95\ub839\uc57d\uce6d\uba85": URBAN,
                "MST": MST,
                "\ubc95\ub839ID": LAW_ID,
                "\uc2dc\ud589\uc77c\uc790": "20240223",
                "\ud604\ud589\uc5ec\ubd80": "\ud604\ud589",
                "OC": SECRET,
            }
        ]
    }
}

DOCUMENT_FIXTURE = {
    "\ubc95\ub839": {
        "\uae30\ubcf8\uc815\ubcf4": {
            "\ubc95\ub839\uba85\ud55c\uae00": URBAN,
            "\ubc95\ub839ID": LAW_ID,
            "\uc2dc\ud589\uc77c\uc790": "20240223",
        },
        "\uc870\ubb38": {
            "\uc870\ubb38\ub2e8\uc704": [
                {
                    "\uc870\ubb38\ubc88\ud638": ARTICLE_3,
                    "\uc870\ubb38\uc81c\ubaa9": "\ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815 \ub4f1",
                    "\uc870\ubb38\ub0b4\uc6a9": "\uc81c3\uc870 \ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed \uc9c0\uc815 \ub0b4\uc6a9",
                },
                {
                    "\uc870\ubb38\ubc88\ud638": "\uc81c4\uc870",
                    "\uc870\ubb38\uc81c\ubaa9": "\uac1c\ubc1c\uacc4\ud68d\uc758 \uc218\ub9bd",
                    "\uc870\ubb38\ub0b4\uc6a9": "\uc81c4\uc870 \uac1c\ubc1c\uacc4\ud68d \uc218\ub9bd \ub0b4\uc6a9",
                },
            ]
        },
    }
}


def _cleanup() -> None:
    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_key == LAW_KEY)).all())
        if law_ids:
            article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
            db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
            if article_ids:
                db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
                db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_article_id.in_(article_ids)))
                db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
            db.execute(delete(Law).where(Law.id.in_(law_ids)))
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.query == URBAN)).all())
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        document_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.mst == MST)).all())
        if document_ids:
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(document_ids)))
        db.commit()
    finally:
        db.close()


def _create_reference(law_name: str = URBAN, article_no: str = ARTICLE_3, article_title: str = "\ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815 \ub4f1") -> int:
    db = SessionLocal()
    try:
        law = Law(law_name=law_name, law_key=LAW_KEY, source="TEST_SOURCE_DO_NOT_USE", mapping_status="PENDING_MOLEG_API_MAPPING")
        db.add(law)
        db.flush()
        article = LawArticle(law_id=law.id, article_key=ARTICLE_KEY, article_number_text=article_no, article_title=article_title, mapping_status=TODO_MOLEG_API_ARTICLE_CHECK)
        db.add(article)
        db.flush()
        reference = ProcedureLegalReference(step_code=STEP_CODE, law_id=law.id, law_article_id=article.id, reference_status=TODO_MOLEG_API_ARTICLE_CHECK, placeholder=TODO_MOLEG_API_ARTICLE_CHECK, notes_json={"reference_quality": "candidate"})
        db.add(reference)
        db.commit()
        return reference.id
    finally:
        db.close()


def _ingest_fixture() -> int:
    db = SessionLocal()
    try:
        provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)
        search_result = provider._normalize_law_search_result(SEARCH_FIXTURE, query=URBAN)
        document = provider._normalize_law_document(DOCUMENT_FIXTURE, fallback_title=URBAN, fallback_mst=MST)
        response = ingest_fixture_document(db=db, query=URBAN, search_result=search_result, document=document)
        assert response.document_id is not None
        return response.document_id
    finally:
        db.close()


def test_verify_preview_uses_official_db_snapshot_before_live_or_mock():
    _cleanup()
    try:
        document_id = _ingest_fixture()
        reference_id = _create_reference()

        response = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [reference_id], "source_mode": "live"})

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_mode"] == "official_db"
        assert item["match_status"] == "matched"
        assert item["source_error"] is False
        assert item["document_id"] == document_id
        assert item["article_count"] == 2
        assert item["evidence_type"] == "official_law_documents_snapshot"
    finally:
        _cleanup()


def test_live_connection_error_does_not_break_when_db_snapshot_exists():
    _cleanup()
    try:
        _ingest_fixture()
        reference_id = _create_reference()

        response = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [reference_id], "source_mode": "live"})

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_mode"] == "official_db"
        assert item["reason_type"] is None
        assert item["source_error"] is False
    finally:
        _cleanup()


def test_no_db_snapshot_keeps_mock_fallback_behavior():
    _cleanup()
    try:
        reference_id = _create_reference(law_name="TEST_LAW_DO_NOT_USE", article_no="TEST_ARTICLE_DO_NOT_USE", article_title="TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE")

        response = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [reference_id]})

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_mode"] == "mock"
        assert item["match_status"] == "matched"
        assert item["source_error"] is False
    finally:
        _cleanup()


def test_live_failure_without_db_snapshot_falls_back_to_mock_safely():
    _cleanup()
    try:
        reference_id = _create_reference(law_name="TEST_LAW_DO_NOT_USE", article_no="TEST_ARTICLE_DO_NOT_USE", article_title="TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE")

        response = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [reference_id], "source_mode": "live"})

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_mode"] in {"fallback", "live", "mock"}
        assert item["match_status"] in {"matched", "source_unavailable", "source_error"}
    finally:
        _cleanup()


def test_snapshot_status_endpoint_reports_counts_and_latest_status():
    _cleanup()
    try:
        _ingest_fixture()

        response = client.get("/api/legal-references/official-law-snapshot")

        assert response.status_code == 200
        data = response.json()
        assert data["document_count"] >= 1
        assert data["article_count"] >= 2
        assert data["ingest_run_count"] >= 1
        assert data["latest_ingest_status"] == "success"
        assert data["source_provider"] == "moleg_open_api"
    finally:
        _cleanup()


def test_duplicate_ingest_reuses_document_id_and_evidence_is_sanitized():
    _cleanup()
    try:
        first_id = _ingest_fixture()
        second_id = _ingest_fixture()

        db = SessionLocal()
        try:
            document_count = db.scalar(select(func.count()).select_from(OfficialLawDocument).where(OfficialLawDocument.mst == MST))
            assert first_id == second_id
            assert document_count == 1
            evidence = db.scalar(select(OfficialLawSourceEvidence).join(OfficialLawIngestRun).where(OfficialLawIngestRun.query == URBAN).order_by(OfficialLawSourceEvidence.id.desc()).limit(1))
            assert evidence is not None
            assert evidence.redaction_applied is True
            assert SECRET not in str(evidence.sanitized_summary_json)
        finally:
            db.close()
    finally:
        _cleanup()

