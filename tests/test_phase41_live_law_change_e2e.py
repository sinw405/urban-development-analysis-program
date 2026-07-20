from __future__ import annotations

import json
from datetime import date

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models import LawChangeImpactEvent, OfficialLawArticleRecord, OfficialLawDocument, ProcedureArticleReviewEvent, ProcedureOfficialArticleCandidate
from app.services.law_version_impact_service import LawVersionImpactService
from app.services.moleg_live_client import MOLEG_LAW_SEARCH_PATH, MOLEG_LAW_SERVICE_PATH, MolegLiveClient, SECRET_REDACTION, redact_secret_values
from app.services.moleg_version_discovery_service import discover_law_versions, ingest_law_versions, normalize_law_id, parse_eflaw_list_response, select_current_previous_pair, select_exact_law_versions
from app.services.moleg_version_diff_service import diff_moleg_versions
from app.services.procedure_article_review_service import confirm_candidate, reject_candidate

client = TestClient(app)
SECRET = "TEST_PHASE41_SECRET_DO_NOT_USE"
LAW_NAME = "Phase41 Live Law"
LAW_ID = "PHASE41-LAW-ID"
OLD_MST = "PHASE41-MST-OLD"
CURRENT_MST = "PHASE41-MST-CURRENT"
OLDER_MST = "PHASE41-MST-OLDER"
PROC = "PROJECT_BASIC_REVIEW"


def _enable(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    get_settings.cache_clear()


def _search_xml(result_code: str = "00") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
  <totalCnt>3</totalCnt><page>1</page><numOfRows>3</numOfRows><resultCode>{result_code}</resultCode><resultMsg>success</resultMsg>
  <law><법령명한글>{LAW_NAME}</법령명한글><법령일련번호>{CURRENT_MST}</법령일련번호><법령ID>{LAW_ID}</법령ID><공포일자>20260701</공포일자><공포번호>2026-1</공포번호><제개정구분명>일부개정</제개정구분명><현행연혁코드>현행</현행연혁코드><시행일자>20260701</시행일자><법령상세링크>/DRF/lawService.do?OC={SECRET}&amp;target=law&amp;MST={CURRENT_MST}&amp;type=HTML</법령상세링크></law>
  <law><법령명한글>{LAW_NAME}</법령명한글><법령일련번호>{OLD_MST}</법령일련번호><법령ID>{LAW_ID}</법령ID><공포일자>20250101</공포일자><공포번호>2025-1</공포번호><제개정구분명>일부개정</제개정구분명><현행연혁코드>연혁</현행연혁코드><시행일자>20250131</시행일자></law>
  <law><법령명한글>{LAW_NAME}</법령명한글><법령일련번호>{OLDER_MST}</법령일련번호><법령ID>{LAW_ID}</법령ID><공포일자>20240101</공포일자><공포번호>2024-1</공포번호><제개정구분명>제정</제개정구분명><현행연혁코드>연혁</현행연혁코드><시행일자>20240131</시행일자></law>
</LawSearch>"""


def _detail_xml(mst: str) -> str:
    if mst == OLD_MST:
        article1 = "old body"
        added = ""
    elif mst == CURRENT_MST:
        article1 = "new body"
        added = "<조문단위><조문번호>3</조문번호><조문제목>기본 신규 사업</조문제목><조문내용>신규 사업 내용</조문내용></조문단위>"
    else:
        article1 = "older body"
        added = ""
    effective = "20250131" if mst == OLD_MST else "20260701" if mst == CURRENT_MST else "20240131"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<법령><기본정보><법령명한글>{LAW_NAME}</법령명한글><법령ID>{LAW_ID}</법령ID><시행일자>{effective}</시행일자></기본정보><조문>
<조문단위><조문번호>1</조문번호><조문제목>기본 사업</조문제목><조문내용>{article1}</조문내용><항내용>{article1}</항내용></조문단위>
<조문단위><조문번호>2</조문번호><조문제목>유지 조문</조문제목><조문내용>same body</조문내용></조문단위>
{added}</조문></법령>"""


def _xml_response(url: str, text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "application/xml"}, request=httpx.Request("GET", url))


def _mock(monkeypatch, search_xml: str | None = None, timeout: bool = False, bad_xml: bool = False, empty_detail: bool = False):
    calls = {"count": 0}

    def fake_get(url, params, **kwargs):
        calls["count"] += 1
        assert params["OC"] == SECRET
        if timeout and calls["count"] == 1:
            raise httpx.TimeoutException("phase41 timeout")
        if MOLEG_LAW_SEARCH_PATH in url:
            return _xml_response(url, search_xml or _search_xml())
        if MOLEG_LAW_SERVICE_PATH in url:
            if bad_xml:
                return _xml_response(url, "<not-closed")
            if empty_detail:
                return _xml_response(url, f"<법령><기본정보><법령명한글>{LAW_NAME}</법령명한글></기본정보><조문 /></법령>")
            return _xml_response(url, _detail_xml(params["MST"]))
        raise AssertionError(url)

    monkeypatch.setattr(httpx, "get", fake_get)
    return calls


def _cleanup():
    db = SessionLocal()
    try:
        candidate_ids = list(db.scalars(select(ProcedureOfficialArticleCandidate.id).where(ProcedureOfficialArticleCandidate.law_id == LAW_ID)).all())
        if candidate_ids:
            db.execute(delete(LawChangeImpactEvent).where(LawChangeImpactEvent.candidate_id.in_(candidate_ids)))
            db.execute(delete(ProcedureArticleReviewEvent).where(ProcedureArticleReviewEvent.candidate_id.in_(candidate_ids)))
            db.execute(delete(ProcedureOfficialArticleCandidate).where(ProcedureOfficialArticleCandidate.id.in_(candidate_ids)))
        db.execute(delete(LawChangeImpactEvent).where(LawChangeImpactEvent.law_id == LAW_ID))
        doc_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.law_id == LAW_ID)).all())
        if doc_ids:
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(doc_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(doc_ids)))
        db.commit()
    finally:
        db.close()


def _client() -> MolegLiveClient:
    return MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, retry_count=1, retry_backoff_seconds=0)



def test_phase41_eflaw_parser_normalizes_filters_deduplicates_and_selects_pair():
    name = "도시개발법"
    decree_name = "도시개발법 시행령"
    payload = {
        "LawSearch": {
            "totalCnt": "5",
            "resultCode": "00",
            "resultMsg": "success",
            "law": [
                {"법령명한글": name, "법령일련번호": "284059", "법령ID": "002024", "공포일자": "20260305", "공포번호": "21447", "제개정구분명": "타법개정", "현행연혁코드": "현행", "시행일자": "20260701", "법령상세링크": f"/DRF/lawService.do?OC={SECRET}&MST=284059"},
                {"법령명한글": name, "법령일련번호": "270001", "법령ID": "2024", "공포일자": "20250101", "공포번호": "20000", "제개정구분명": "일부개정", "현행연혁코드": "연혁", "시행일자": "20250131"},
                {"법령명한글": name, "법령일련번호": "270001", "법령ID": "002024", "공포일자": "20250101", "공포번호": "20000", "제개정구분명": "일부개정", "현행연혁코드": "연혁", "시행일자": "20250131"},
                {"법령명한글": decree_name, "법령일련번호": "287279", "법령ID": "003421", "시행일자": "20260701"},
                {"법령명한글": name, "법령일련번호": "bad-id", "법령ID": "999999", "시행일자": "20260701"},
            ],
        }
    }
    parsed = parse_eflaw_list_response(payload)
    assert parsed["result_code"] == "00"
    assert parsed["total_cnt"] == 5
    assert parsed["laws"][0]["law_id_normalized"] == "2024"
    assert "[REDACTED]" in parsed["laws"][0]["detail_link_sanitized"]
    versions = select_exact_law_versions(parsed["laws"], name, normalized_law_id="2024")
    assert [item.mst for item in versions] == ["284059", "270001"]
    pair = select_current_previous_pair(versions)
    assert pair is not None
    assert pair[0].mst == "270001" and pair[1].mst == "284059"
    assert normalize_law_id("002024") == "2024"


def test_phase41_eflaw_parser_accepts_alternate_root_and_empty_result():
    name = "도시개발법"
    payload = {"response": {"body": {"items": {"item": {"법령명한글": name, "법령일련번호": "1", "법령ID": "002024"}}, "resultCode": "00"}}}
    parsed = parse_eflaw_list_response(payload)
    assert len(parsed["laws"]) == 1
    empty = parse_eflaw_list_response({"LawSearch": {"resultCode": "00", "law": []}})
    assert empty["laws"] == []


def test_phase41_eflaw_parser_rejects_result_code_error():
    try:
        parse_eflaw_list_response({"LawSearch": {"resultCode": "99", "resultMsg": "failure", "law": []}})
    except Exception as exc:
        assert "api_error_response" in str(exc)
    else:
        raise AssertionError("expected parser error")

def test_phase41_version_history_parsing_and_pair_selection(monkeypatch):
    _enable(monkeypatch); _mock(monkeypatch)
    result = discover_law_versions(_client(), LAW_NAME, max_versions=5)
    assert result.status == "ok"
    assert len(result.versions) == 3
    assert result.versions[0].mst == CURRENT_MST
    assert result.versions[0].promulgation_number == "2026-1"
    pair = select_current_previous_pair(result.versions)
    assert pair is not None
    assert pair[0].mst == OLD_MST and pair[1].mst == CURRENT_MST
    dumped = json.dumps(result.to_dict(), ensure_ascii=False, default=str)
    assert SECRET not in dumped


def test_phase41_ingest_realistic_different_mst_and_diff(monkeypatch):
    _cleanup(); _enable(monkeypatch); _mock(monkeypatch)
    db = SessionLocal()
    try:
        discovery = discover_law_versions(_client(), LAW_NAME, max_versions=2)
        assert discovery.selected_pair is not None
        ingest = ingest_law_versions(db, _client(), list(discovery.selected_pair), dry_run=False)
        assert ingest.status == "completed"
        assert ingest.parsed_article_count == 5
        diff = diff_moleg_versions(db, LAW_NAME, OLD_MST, CURRENT_MST)
        assert diff.status == "ok"
        assert len(diff.changed) == 1
        assert len(diff.added) == 1
        assert len(diff.unchanged) == 1
        assert len(diff.removed) == 0
        assert all(item["raw_payload_stored"] is False for item in ingest.provenance)
    finally:
        db.close(); _cleanup(); get_settings.cache_clear()


def test_phase41_error_empty_bad_xml_timeout_and_redaction(monkeypatch):
    _enable(monkeypatch); _mock(monkeypatch, search_xml=_search_xml(result_code="99"))
    result = discover_law_versions(_client(), LAW_NAME, max_versions=2)
    assert result.status in {"source_error", "no_versions", "ok"}
    _mock(monkeypatch, bad_xml=True)
    db = SessionLocal()
    try:
        discovery = discover_law_versions(_client(), LAW_NAME, max_versions=2)
        assert discovery.selected_pair is not None
        bad = ingest_law_versions(db, _client(), list(discovery.selected_pair), dry_run=True)
        assert bad.status == "source_error"
    finally:
        db.close()
    _mock(monkeypatch, empty_detail=True)
    db = SessionLocal()
    try:
        discovery = discover_law_versions(_client(), LAW_NAME, max_versions=2)
        assert discovery.selected_pair is not None
        empty = ingest_law_versions(db, _client(), list(discovery.selected_pair), dry_run=True)
        assert empty.status == "source_error"
    finally:
        db.close()
    assert redact_secret_values({"OC": SECRET, "url": f"https://x.test?OC={SECRET}"}, SECRET)["OC"] == SECRET_REDACTION
    get_settings.cache_clear()


def test_phase41_live_candidate_not_auto_confirm_explicit_review_idempotency_and_analyze(monkeypatch):
    _cleanup(); _enable(monkeypatch); _mock(monkeypatch)
    db = SessionLocal()
    try:
        discovery = discover_law_versions(_client(), LAW_NAME, max_versions=2)
        assert discovery.selected_pair is not None
        ingest_law_versions(db, _client(), list(discovery.selected_pair), dry_run=False)
        current_doc = db.scalar(select(OfficialLawDocument).where(OfficialLawDocument.law_id == LAW_ID, OfficialLawDocument.mst == CURRENT_MST))
        changed_old = db.scalar(select(OfficialLawArticleRecord).join(OfficialLawDocument).where(OfficialLawDocument.mst == OLD_MST, OfficialLawArticleRecord.article_no == "1"))
        candidate = ProcedureOfficialArticleCandidate(
            procedure_code="PROJECT_BASIC_REVIEW",
            procedure_name="Project basic review",
            law_title=LAW_NAME,
            law_id=LAW_ID,
            mst=OLD_MST,
            document_id=changed_old.document_id,
            article_id=changed_old.id,
            article_no=changed_old.article_no,
            article_title=changed_old.article_title,
            match_method="phase41_fixture_controlled",
            match_score=99,
            match_status="candidate",
            source_mode="official_db",
            source_mode_detail="official_db",
            confidence_level="high",
            is_confirmed=False,
            provider_reason="Phase41 controlled review candidate only.",
        )
        db.add(candidate); db.commit(); cid = candidate.id
        assert db.get(ProcedureOfficialArticleCandidate, cid).is_confirmed is False
        assert confirm_candidate(db, cid, "phase41_reviewer", "explicit confirm for controlled test").status == "ok"
        first = LawVersionImpactService(db).analyze(LAW_NAME, OLD_MST, CURRENT_MST, dry_run=False)
        second = LawVersionImpactService(db).analyze(LAW_NAME, OLD_MST, CURRENT_MST, dry_run=False)
        assert first.needs_revalidation_count == 1
        assert first.generated_event_count >= 1
        assert second.skipped_duplicate_event_count >= 1
        assert db.scalar(select(func.count()).select_from(ProcedureArticleReviewEvent).where(ProcedureArticleReviewEvent.candidate_id == cid)) == 1
    finally:
        db.close()
    response = client.post("/api/analyze", json={"project_name":"p41","location":"x","area_square_meters":100000,"implementation_method":"mixed","implementer_type":"public","local_government":"x"})
    assert response.status_code == 200
    target = next(step for step in response.json()["procedures"] if step["step_code"] == PROC)
    assert target["reference_status"] == "needs_revalidation"
    db = SessionLocal()
    try:
        assert reject_candidate(db, cid, "phase41_reviewer", "explicit reject after test").status == "ok"
        after_reject = client.post("/api/analyze", json={"project_name":"p41","location":"x","area_square_meters":100000,"implementation_method":"mixed","implementer_type":"public","local_government":"x"}).json()
        target = next(step for step in after_reject["procedures"] if step["step_code"] == PROC)
        assert all(ref.get("notes", {}).get("candidate_id") != cid for ref in target["legal_references"])
        assert db.scalar(select(func.count()).select_from(ProcedureArticleReviewEvent).where(ProcedureArticleReviewEvent.candidate_id == cid)) == 2
    finally:
        db.close(); _cleanup(); get_settings.cache_clear()


def test_phase41_rollback_preserves_counts(monkeypatch):
    _cleanup(); _enable(monkeypatch); _mock(monkeypatch)
    db = SessionLocal()
    try:
        discovery = discover_law_versions(_client(), LAW_NAME, max_versions=2)
        assert discovery.selected_pair is not None
        before = db.scalar(select(func.count()).select_from(OfficialLawDocument).where(OfficialLawDocument.law_id == LAW_ID))
        rolled = ingest_law_versions(db, _client(), list(discovery.selected_pair), dry_run=False, force_rollback=True)
        after = db.scalar(select(func.count()).select_from(OfficialLawDocument).where(OfficialLawDocument.law_id == LAW_ID))
        assert rolled.status == "rolled_back"
        assert before == after
    finally:
        db.close(); _cleanup(); get_settings.cache_clear()
