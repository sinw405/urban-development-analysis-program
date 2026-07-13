from __future__ import annotations

import json

import httpx
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
)
from app.services.law_version_service import get_article_versions
from app.services.moleg_live_client import MOLEG_LAW_SEARCH_PATH, MOLEG_LAW_SERVICE_PATH
from app.services.moleg_live_ingest_service import run_moleg_live_ingest, select_exact_law_candidate
from app.services.official_law_source import MolegOpenApiLawSourceProvider

client = TestClient(app)
SECRET = "TEST_PHASE37_SECRET_DO_NOT_USE"
LAW_NAME = "Dummy Live Law"
SIMILAR_LAW_NAME = "Dummy Live Law Enforcement Decree"
LAW_ID = "DUMMY-LAW-ID-37"
MST = "DUMMY-MST-37"
ARTICLE_NO = "DUMMY-001"

SEARCH_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
  <totalCnt>2</totalCnt>
  <page>1</page>
  <numOfRows>2</numOfRows>
  <resultCode>00</resultCode>
  <resultMsg>success</resultMsg>
  <law>
    <법령명한글><![CDATA[{SIMILAR_LAW_NAME}]]></법령명한글>
    <법령일련번호>DUMMY-MST-SIMILAR</법령일련번호>
    <법령ID>DUMMY-SIMILAR-ID</법령ID>
    <법령구분명>Dummy Type</법령구분명>
    <시행일자>20990101</시행일자>
  </law>
  <law>
    <법령명한글><![CDATA[{LAW_NAME}]]></법령명한글>
    <법령일련번호>{MST}</법령일련번호>
    <법령ID>{LAW_ID}</법령ID>
    <공포일자>20981212</공포일자>
    <공포번호>DUMMY-PROM-37</공포번호>
    <제개정구분명>Dummy Revision</제개정구분명>
    <소관부처명>Dummy Ministry</소관부처명>
    <법령구분명>Dummy Act</법령구분명>
    <시행일자>20990101</시행일자>
    <법령상세링크>/DRF/lawService.do?OC={SECRET}&amp;target=law&amp;MST={MST}&amp;type=HTML&amp;efYd=20990101</법령상세링크>
  </law>
</LawSearch>
"""

DETAIL_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<법령>
  <기본정보>
    <법령명한글>{LAW_NAME}</법령명한글>
    <법령ID>{LAW_ID}</법령ID>
    <시행일자>20990101</시행일자>
  </기본정보>
  <조문>
    <조문단위>
      <조문번호>{ARTICLE_NO}</조문번호>
      <조문제목>Dummy Live Article Title</조문제목>
      <조문내용>Dummy live article body for parser fixture only.</조문내용>
      <항내용>Dummy paragraph for fixture only.</항내용>
    </조문단위>
  </조문>
</법령>
"""

DETAIL_XML_UPDATED = DETAIL_XML.replace("Dummy live article body for parser fixture only.", "Dummy live article body updated for parser fixture only.")


def _clear_settings() -> None:
    get_settings.cache_clear()


def _enable_live(monkeypatch) -> None:
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    _clear_settings()


def _xml_response(url: str, text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "application/xml"}, request=httpx.Request("GET", url))


def _mock_moleg(monkeypatch, detail_xml: str = DETAIL_XML, search_xml: str = SEARCH_XML) -> None:
    def fake_get(url, params, **kwargs):
        assert params["OC"] == SECRET
        if MOLEG_LAW_SEARCH_PATH in url:
            return _xml_response(url, search_xml)
        if MOLEG_LAW_SERVICE_PATH in url:
            assert params["MST"] == MST
            assert params["type"] == "XML"
            return _xml_response(url, detail_xml)
        raise AssertionError(url)

    monkeypatch.setattr(httpx, "get", fake_get)


def _cleanup() -> None:
    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_key == f"moleg:{LAW_ID}")).all())
        if law_ids:
            article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
            db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
            if article_ids:
                db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_article_id.in_(article_ids)))
                db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
                db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
            db.execute(delete(Law).where(Law.id.in_(law_ids)))
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.query == LAW_NAME)).all())
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


def _counts() -> tuple[int, int, int, int, int]:
    db = SessionLocal()
    try:
        return (
            db.scalar(select(func.count()).select_from(Law).where(Law.law_key == f"moleg:{LAW_ID}")) or 0,
            db.scalar(select(func.count()).select_from(LawArticle).join(Law).where(Law.law_key == f"moleg:{LAW_ID}")) or 0,
            db.scalar(select(func.count()).select_from(LawArticleVersion).join(LawArticle).join(Law).where(Law.law_key == f"moleg:{LAW_ID}")) or 0,
            db.scalar(select(func.count()).select_from(OfficialLawDocument).where(OfficialLawDocument.mst == MST)) or 0,
            db.scalar(select(func.count()).select_from(OfficialLawArticleRecord).join(OfficialLawDocument).where(OfficialLawDocument.mst == MST)) or 0,
        )
    finally:
        db.close()


def test_phase37_dry_run_does_not_change_db(monkeypatch):
    _cleanup()
    _enable_live(monkeypatch)
    _mock_moleg(monkeypatch)
    before = _counts()
    db = SessionLocal()
    try:
        result = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=True)
    finally:
        db.close()
        _clear_settings()
    after = _counts()
    try:
        assert result.status == "ready"
        assert result.final_reason_type == "ok"
        assert result.counters.inserted_law_count == 1
        assert result.counters.inserted_article_count == 1
        assert result.counters.inserted_article_version_count == 1
        assert before == after
    finally:
        _cleanup()


def test_phase37_apply_persists_and_second_apply_is_idempotent(monkeypatch):
    _cleanup()
    _enable_live(monkeypatch)
    _mock_moleg(monkeypatch)
    db = SessionLocal()
    try:
        first = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=False)
        second = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=False)
        assert first.status == "completed"
        assert first.counters.inserted_law_count == 1
        assert first.counters.inserted_article_count == 1
        assert first.counters.inserted_article_version_count == 1
        assert first.counters.inserted_official_document_count == 1
        assert first.counters.inserted_official_article_count == 1
        assert second.status == "completed"
        assert second.counters.inserted_law_count == 0
        assert second.counters.inserted_article_count == 0
        assert second.counters.inserted_article_version_count == 0
        assert second.counters.inserted_official_document_count == 0
        assert second.counters.inserted_official_article_count == 0
        assert _counts() == (1, 1, 1, 1, 1)
        law = db.scalar(select(Law).where(Law.law_key == f"moleg:{LAW_ID}"))
        assert law is not None
        article = db.scalar(select(LawArticle).where(LawArticle.law_id == law.id))
        assert article is not None
        version = db.scalar(select(LawArticleVersion).where(LawArticleVersion.law_article_id == article.id))
        assert version is not None
        assert version.raw_payload_json is None
        assert version.source == f"MOLEG_LIVE:{MST}"
    finally:
        db.close()
        _clear_settings()
        _cleanup()


def test_phase37_updated_live_article_updates_existing_version(monkeypatch):
    _cleanup()
    _enable_live(monkeypatch)
    _mock_moleg(monkeypatch)
    db = SessionLocal()
    try:
        first = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=False)
        assert first.status == "completed"
        _mock_moleg(monkeypatch, detail_xml=DETAIL_XML_UPDATED)
        second = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=False)
        assert second.counters.updated_article_version_count == 1
        assert second.counters.inserted_article_version_count == 0
        version = db.scalar(select(LawArticleVersion).join(LawArticle).join(Law).where(Law.law_key == f"moleg:{LAW_ID}"))
        assert version is not None
        assert "updated" in (version.article_text or "")
    finally:
        db.close()
        _clear_settings()
        _cleanup()


def test_phase37_rollback_after_persist_leaves_no_rows(monkeypatch):
    _cleanup()
    _enable_live(monkeypatch)
    _mock_moleg(monkeypatch)
    before = _counts()
    db = SessionLocal()
    try:
        result = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=False, force_rollback_after_persist=True)
    finally:
        db.close()
        _clear_settings()
    try:
        assert result.status == "rolled_back"
        assert result.rollback is True
        assert _counts() == before
    finally:
        _cleanup()


def test_phase37_as_of_lookup_and_missing_date_behavior(monkeypatch):
    _cleanup()
    _enable_live(monkeypatch)
    _mock_moleg(monkeypatch)
    db = SessionLocal()
    try:
        result = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=False)
        assert result.status == "completed"
        law = db.scalar(select(Law).where(Law.law_key == f"moleg:{LAW_ID}"))
        article = db.scalar(select(LawArticle).where(LawArticle.law_id == law.id))
        previous = get_article_versions(db=db, article_id=article.id, as_of=__import__('datetime').date(2025, 1, 1))
        current = get_article_versions(db=db, article_id=article.id, as_of=__import__('datetime').date(2099, 1, 1))
        future = get_article_versions(db=db, article_id=article.id, as_of=__import__('datetime').date(2100, 1, 1))
        assert all(item.temporal_status == "scheduled" for item in previous)
        assert any(item.temporal_status == "current" for item in current)
        assert any(item.temporal_status == "current" for item in future)
        missing = client.get("/api/laws/999999999/articles")
        assert missing.status_code == 404
    finally:
        db.close()
        _clear_settings()
        _cleanup()


def test_phase37_similar_law_name_is_not_selected():
    provider = MolegOpenApiLawSourceProvider(base_url="http://www.law.go.kr", api_key=SECRET)
    payload = {"LawSearch": {"law": [{"법령명한글": SIMILAR_LAW_NAME, "법령일련번호": "SIMILAR-MST", "법령ID": "SIMILAR-ID", "시행일자": "20990101"}]}}
    search_result = provider._normalize_law_search_result(payload=payload, query=LAW_NAME)
    assert select_exact_law_candidate(search_result, LAW_NAME) is None


def test_phase37_secret_raw_payload_and_diagnostic_analyze_regression(monkeypatch):
    _cleanup()
    _enable_live(monkeypatch)
    _mock_moleg(monkeypatch)
    db = SessionLocal()
    try:
        result = run_moleg_live_ingest(db=db, law_name=LAW_NAME, dry_run=False)
        dumped = json.dumps(result.to_dict(), ensure_ascii=False, default=str)
        assert SECRET not in dumped
        assert result.raw_payload_stored is False
        assert result.secret_exposed is False
        evidence = db.scalar(select(OfficialLawSourceEvidence).join(OfficialLawIngestRun).where(OfficialLawIngestRun.query == LAW_NAME).order_by(OfficialLawSourceEvidence.id.desc()).limit(1))
        assert evidence is not None
        assert evidence.raw_available is False
        assert SECRET not in json.dumps(evidence.sanitized_summary_json, ensure_ascii=False)

        diagnostic = client.get("/api/legal-references/moleg/diagnostic")
        assert diagnostic.status_code == 200
        analyze = client.post("/api/analyze", json={"project_name": "Phase37 Analyze Smoke", "location": "Test", "area_square_meters": 100000, "implementation_method": "expropriation_or_use", "implementer_type": "public", "local_government": "Test LG"})
        assert analyze.status_code == 200
        assert len(analyze.json()["procedures"]) == 13
    finally:
        db.close()
        _clear_settings()
        _cleanup()
