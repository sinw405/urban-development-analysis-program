from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Law, LawArticle, LawArticleVersion, OfficialLawArticleRecord, OfficialLawDocument, OfficialLawIngestRun, OfficialLawSourceEvidence, ProcedureLegalReference
from app.services.legal_reference_service import TODO_MOLEG_API_ARTICLE_CHECK

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
JSON_MANIFEST = FIXTURES / "moleg_seed_manifest.json"
XML_MANIFEST = FIXTURES / "moleg_seed_manifest_xml.json"
PLACEHOLDER_MANIFEST = FIXTURES / "moleg_seed_manifest_placeholder.json"
MISSING_SOURCE_MANIFEST = FIXTURES / "moleg_seed_manifest_missing_source.json"
HIGH_COUNT_MANIFEST = FIXTURES / "moleg_seed_manifest_high_count.json"
LAW_NAME = "TEST_PHASE27_MANUAL_LAW_DO_NOT_USE"
ARTICLE_NO = "TEST_PHASE27_ARTICLE_JSON"
LAW_KEY = "TEST_PHASE28_SEED_LAW_KEY_DO_NOT_USE"
ARTICLE_KEY = "TEST_PHASE28_SEED_ARTICLE_KEY_DO_NOT_USE"
MST_JSON = "PHASE27_MANUAL_MST_JSON"
MST_XML = "PHASE27_MANUAL_MST_XML"


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
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.source_mode == "official_seed")).all())
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        document_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.mst.in_([MST_JSON, MST_XML]))).all())
        if document_ids:
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(document_ids)))
        db.commit()
    finally:
        db.close()


def _create_reference() -> int:
    db = SessionLocal()
    try:
        law = Law(law_name=LAW_NAME, law_key=LAW_KEY, source="TEST_PHASE28", mapping_status="PENDING_MOLEG_API_MAPPING")
        db.add(law)
        db.flush()
        article = LawArticle(law_id=law.id, article_key=ARTICLE_KEY, article_number_text=ARTICLE_NO, article_title="TEST_PHASE27_ARTICLE_TITLE_JSON", mapping_status=TODO_MOLEG_API_ARTICLE_CHECK)
        db.add(article)
        db.flush()
        ref = ProcedureLegalReference(step_code="PROJECT_BASIC_REVIEW", law_id=law.id, law_article_id=article.id, reference_status=TODO_MOLEG_API_ARTICLE_CHECK, placeholder=TODO_MOLEG_API_ARTICLE_CHECK, notes_json={"reference_quality": "candidate"})
        db.add(ref)
        db.commit()
        return ref.id
    finally:
        db.close()


def test_placeholder_manifest_is_blocked():
    _cleanup()
    try:
        response = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(PLACEHOLDER_MANIFEST)})
        data = response.json()
        assert response.status_code == 200
        assert data["success"] is False
        assert data["status"] == "validation_error"
        assert data["reason_type"] == "validation_error"
    finally:
        _cleanup()


def test_missing_source_file_returns_validation_error():
    response = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(MISSING_SOURCE_MANIFEST)})
    data = response.json()
    assert response.status_code == 200
    assert data["success"] is False
    assert data["reason_type"] == "validation_error"
    assert "source_file" in data["error_message_sanitized"]


def test_seed_json_import_stores_document_articles_run_and_evidence():
    _cleanup()
    try:
        response = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(JSON_MANIFEST)})
        data = response.json()
        assert response.status_code == 200
        assert data["success"] is True
        assert data["source_mode"] == "official_seed"
        assert data["source_mode_detail"] == "official_seed_db"
        assert data["article_count"] == 2
        assert data["evidence_type"] == "official_seed_normalized_summary"

        db = SessionLocal()
        try:
            document = db.get(OfficialLawDocument, data["document_id"])
            assert document is not None
            assert document.source_mode == "official_seed"
            assert document.mst == MST_JSON
            assert db.scalar(select(func.count()).select_from(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == document.id)) == 2
            run = db.get(OfficialLawIngestRun, data["ingest_run_id"])
            assert run is not None
            assert run.status == "success"
            evidence = db.scalar(select(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id == run.id))
            assert evidence is not None
            assert evidence.redaction_applied is True
            assert "TEST_PHASE27_ARTICLE_TEXT_JSON" not in str(evidence.sanitized_summary_json)
        finally:
            db.close()
    finally:
        _cleanup()


def test_seed_xml_import_success_or_safe_parse_error():
    _cleanup()
    try:
        response = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(XML_MANIFEST)})
        data = response.json()
        assert response.status_code == 200
        assert data["secret_exposed"] is False
        assert data["status"] in {"success", "source_error"}
        if data["success"]:
            assert data["article_count"] == 1
        else:
            assert data["reason_type"] in {"parse_error", "invalid_response"}
    finally:
        _cleanup()


def test_expected_min_article_count_warning_is_returned():
    _cleanup()
    try:
        response = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(HIGH_COUNT_MANIFEST)})
        data = response.json()
        assert response.status_code == 200
        assert data["success"] is True
        assert any("expected_min_article_count" in warning for warning in data["warnings"])
    finally:
        _cleanup()


def test_seed_import_snapshot_and_verify_preview_source_mode_detail():
    _cleanup()
    try:
        seed = client.post("/api/legal-references/official-law-seed-import", json={"manifest_path": str(JSON_MANIFEST)}).json()
        ref_id = _create_reference()
        preview = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [ref_id], "source_mode": "live"})
        snapshot = client.get("/api/legal-references/official-law-snapshot")

        item = preview.json()["items"][0]
        assert item["source_mode"] == "official_db"
        assert item["source_mode_detail"] == "official_seed_db"
        assert item["document_id"] == seed["document_id"]
        assert item["article_count"] == 2
        assert item["source_error"] is False

        snapshot_data = snapshot.json()
        assert snapshot_data["seed_import_count"] >= 1
        assert snapshot_data["latest_seed_import_status"] == "success"
        assert snapshot_data["latest_seed_law_title"] == LAW_NAME
        assert "official_seed" in snapshot_data["source_modes"]
    finally:
        _cleanup()
