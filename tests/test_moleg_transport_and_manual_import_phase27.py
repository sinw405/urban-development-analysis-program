from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.config import get_settings
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
    ProcedureOfficialArticleCandidate,
)
from app.services.legal_reference_service import TODO_MOLEG_API_ARTICLE_CHECK
from app.services.moleg_transport_probe_service import diagnose_moleg_transport

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
JSON_FIXTURE = ROOT / "tests" / "fixtures" / "moleg_manual_import_sample.json"
XML_FIXTURE = ROOT / "tests" / "fixtures" / "moleg_manual_import_sample.xml"
LAW_KEY = "TEST_PHASE27_LAW_KEY_DO_NOT_USE"
ARTICLE_KEY = "TEST_PHASE27_ARTICLE_KEY_DO_NOT_USE"
LAW_NAME = "TEST_PHASE27_MANUAL_LAW_DO_NOT_USE"
ARTICLE_NO = "TEST_PHASE27_ARTICLE_JSON"
MST_JSON = "PHASE27_MANUAL_MST_JSON"
MST_XML = "PHASE27_MANUAL_MST_XML"
SECRET = "TEST_PHASE27_SECRET_DO_NOT_USE"


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
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.query.in_([LAW_NAME, "TEST_PHASE27_MANUAL_XML_LAW_DO_NOT_USE", JSON_FIXTURE.name, XML_FIXTURE.name]))).all())
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        document_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.mst.in_([MST_JSON, MST_XML]))).all())
        if document_ids:
            db.execute(delete(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(document_ids)))
        db.commit()
    finally:
        db.close()


def _create_reference() -> int:
    db = SessionLocal()
    try:
        law = Law(law_name=LAW_NAME, law_key=LAW_KEY, source="TEST_PHASE27", mapping_status="PENDING_MOLEG_API_MAPPING")
        db.add(law)
        db.flush()
        article = LawArticle(law_id=law.id, article_key=ARTICLE_KEY, article_number_text=ARTICLE_NO, article_title="TEST_PHASE27_ARTICLE_TITLE_JSON", mapping_status=TODO_MOLEG_API_ARTICLE_CHECK)
        db.add(article)
        db.flush()
        reference = ProcedureLegalReference(step_code="PROJECT_BASIC_REVIEW", law_id=law.id, law_article_id=article.id, reference_status=TODO_MOLEG_API_ARTICLE_CHECK, placeholder=TODO_MOLEG_API_ARTICLE_CHECK, notes_json={"reference_quality": "candidate"})
        db.add(reference)
        db.commit()
        return reference.id
    finally:
        db.close()


def test_transport_diagnostic_no_secret_is_safe(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    get_settings.cache_clear()
    try:
        result = diagnose_moleg_transport()
        dumped = str(result.model_dump())
        assert result.live_configured is False
        assert result.has_secret is False
        assert result.secret_exposed is False
        assert SECRET not in dumped
    finally:
        get_settings.cache_clear()


def test_transport_diagnostic_dns_failure_returns_json_without_secret(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    get_settings.cache_clear()

    def fake_getaddrinfo(host, port):
        raise OSError("getaddrinfo failed")

    monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)
    try:
        response = client.get("/api/legal-references/moleg-transport-diagnostic")
        data = response.json()
        assert response.status_code == 200
        assert data["reason_type"] == "dns_error"
        assert data["dns_ok"] is None
        assert data["secret_exposed"] is False
        assert SECRET not in str(data)
        assert "[REDACTED]" in (data["final_url_sanitized"] or "")
    finally:
        get_settings.cache_clear()


def test_transport_diagnostic_http_error_after_socket_tls(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "http://example.test")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    get_settings.cache_clear()

    class FakeSocket:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("socket.getaddrinfo", lambda host, port: [(None, None, None, None, None)])
    monkeypatch.setattr("socket.create_connection", lambda address, timeout: FakeSocket())
    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: httpx.Response(503, text="service unavailable", request=httpx.Request("GET", url)))
    try:
        result = diagnose_moleg_transport()
        assert result.dns_ok is True
        assert result.socket_ok is True
        assert result.http_ok is False
        assert result.endpoint_ok is False
        assert result.reason_type == "http_error_status"
        assert result.secret_exposed is False
        assert SECRET not in str(result.model_dump())
    finally:
        get_settings.cache_clear()


def test_manual_import_json_stores_document_articles_and_sanitized_evidence():
    _cleanup()
    try:
        response = client.post("/api/legal-references/official-law-manual-import", json={"file_path": str(JSON_FIXTURE), "query": LAW_NAME})
        data = response.json()
        assert response.status_code == 200
        assert data["status"] == "success"
        assert data["source_mode"] == "official_manual"
        assert data["document_id"] is not None
        assert data["article_count"] == 2

        db = SessionLocal()
        try:
            document = db.get(OfficialLawDocument, data["document_id"])
            assert document is not None
            assert document.source_mode == "official_manual"
            assert document.law_title == LAW_NAME
            assert document.mst == MST_JSON
            articles = db.scalars(select(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == document.id)).all()
            assert len(articles) == 2
            evidence = db.scalar(select(OfficialLawSourceEvidence).join(OfficialLawIngestRun).where(OfficialLawIngestRun.id == data["ingest_run_id"]))
            assert evidence is not None
            assert evidence.redaction_applied is True
            assert "조문내용" not in str(evidence.sanitized_summary_json)
        finally:
            db.close()
    finally:
        _cleanup()


def test_manual_import_xml_stores_or_returns_safe_parse_error():
    _cleanup()
    try:
        response = client.post("/api/legal-references/official-law-manual-import", json={"file_path": str(XML_FIXTURE), "query": "TEST_PHASE27_MANUAL_XML_LAW_DO_NOT_USE"})
        data = response.json()
        assert response.status_code == 200
        assert data["secret_exposed"] is False
        assert data["status"] in {"success", "source_error"}
        if data["status"] == "success":
            assert data["article_count"] == 1
            assert data["document_id"] is not None
        else:
            assert data["reason_type"] in {"parsing_error", "invalid_response_format", "parse_error", "invalid_response"}
    finally:
        _cleanup()


def test_manual_import_snapshot_and_verify_preview_use_db_first():
    _cleanup()
    try:
        import_response = client.post("/api/legal-references/official-law-manual-import", json={"file_path": str(JSON_FIXTURE), "query": LAW_NAME})
        document_id = import_response.json()["document_id"]
        reference_id = _create_reference()

        preview = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [reference_id], "source_mode": "live"})
        snapshot = client.get("/api/legal-references/official-law-snapshot")

        item = preview.json()["items"][0]
        assert preview.status_code == 200
        assert item["source_mode"] == "official_db"
        assert item["match_status"] == "matched"
        assert item["document_id"] == document_id
        assert item["article_count"] == 2
        assert item["source_error"] is False

        snapshot_data = snapshot.json()
        assert snapshot.status_code == 200
        assert snapshot_data["manual_import_count"] >= 1
        assert "official_manual" in snapshot_data["source_modes"]
        assert snapshot_data["latest_manual_import_status"] == "success"
    finally:
        _cleanup()


def test_manual_import_duplicate_reuses_document_id():
    _cleanup()
    try:
        first = client.post("/api/legal-references/official-law-manual-import", json={"file_path": str(JSON_FIXTURE), "query": LAW_NAME}).json()
        second = client.post("/api/legal-references/official-law-manual-import", json={"file_path": str(JSON_FIXTURE), "query": LAW_NAME}).json()
        assert first["document_id"] == second["document_id"]
        db = SessionLocal()
        try:
            count = db.scalar(select(func.count()).select_from(OfficialLawDocument).where(OfficialLawDocument.mst == MST_JSON))
            assert count == 1
        finally:
            db.close()
    finally:
        _cleanup()
