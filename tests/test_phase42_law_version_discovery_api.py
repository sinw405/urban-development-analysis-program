from __future__ import annotations

import json
from datetime import UTC, date, datetime

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models import LawChangeImpactEvent, OfficialLawArticleRecord, OfficialLawDocument, ProcedureArticleReviewEvent, ProcedureOfficialArticleCandidate
from app.services.moleg_live_client import MOLEG_LAW_SEARCH_PATH, MolegLiveClient, parse_response
from app.services.moleg_version_discovery_service import (
    discover_law_versions,
    normalize_law_name,
    normalize_law_version,
    parse_eflaw_list_response,
    select_exact_law_versions,
    select_latest_version_pair,
    sort_law_versions,
    validate_version_pair,
)

client = TestClient(app)
SECRET = "TEST_PHASE42_SECRET_DO_NOT_USE"
LAW_NAME = "Phase42 Live Law"
LAW_ID = "PHASE42-LAW-ID"
FROM_MST = "420001"
TO_MST = "420002"


def _enable(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    get_settings.cache_clear()


def _client() -> MolegLiveClient:
    return MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, retry_count=0, retry_backoff_seconds=0)


def _xml_response(url: str, text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "application/xml"}, request=httpx.Request("GET", url))


def _law_xml(mst: str, name: str = LAW_NAME, effective: str = "20260101", promulgation: str = "20250101", law_id: str = LAW_ID) -> str:
    return (
        f"<law><법령명한글>{name}</법령명한글><법령일련번호>{mst}</법령일련번호>"
        f"<법령ID>{law_id}</법령ID><공포일자>{promulgation}</공포일자><현행연혁코드>연혁</현행연혁코드>"
        f"<시행일자>{effective}</시행일자><법령상세링크>/DRF/lawService.do?OC={SECRET}&amp;MST={mst}</법령상세링크></law>"
    )


def _search_xml(page: int, total: int, rows: int, items: list[str], result_code: str = "00") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<LawSearch><totalCnt>{total}</totalCnt><page>{page}</page><numOfRows>{rows}</numOfRows>"
        f"<resultCode>{result_code}</resultCode><resultMsg>success</resultMsg>{''.join(items)}</LawSearch>"
    )


def _mock_pages(monkeypatch, pages: dict[int, str]):
    calls: list[int] = []

    def fake_get(url, params, **kwargs):
        assert params["OC"] == SECRET
        calls.append(int(params["page"]))
        return _xml_response(url, pages[int(params["page"])])

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


def _doc(db, mst: str, eff: date) -> OfficialLawDocument:
    row = OfficialLawDocument(
        source_provider="moleg_open_api",
        source_mode="live",
        law_title=LAW_NAME,
        law_short_title=None,
        law_id=LAW_ID,
        mst=mst,
        promulgation_date=eff,
        enforcement_date=eff,
        is_current=mst == TO_MST,
        document_status="normalized",
        normalized_at=datetime.now(UTC),
        provider_reason="PHASE42 fixture only.",
        sanitized_source_url="https://example.invalid/moleg/phase42",
    )
    db.add(row)
    db.flush()
    return row


def _article(db, doc: OfficialLawDocument, text: str) -> None:
    db.add(OfficialLawArticleRecord(document_id=doc.id, article_no="1", article_title="basic", article_text=text, paragraphs_json=[text], source_anchor=None, source_hint="PHASE42 fixture only.", sort_order=1))


def _fixture_docs():
    db = SessionLocal()
    try:
        before = _doc(db, FROM_MST, date(2025, 1, 1))
        after = _doc(db, TO_MST, date(2026, 1, 1))
        _article(db, before, "old body")
        _article(db, after, "new body")
        db.commit()
    finally:
        db.close()


def test_phase42_pagination_requests_two_pages_and_merges_188_items(monkeypatch):
    _enable(monkeypatch)
    page1 = [_law_xml(str(410000 + i), effective="20250101") for i in range(100)]
    page2 = [_law_xml(str(410100 + i), effective="20260101") for i in range(88)]
    calls = _mock_pages(monkeypatch, {1: _search_xml(1, 188, 100, page1), 2: _search_xml(2, 188, 100, page2)})
    result = discover_law_versions(_client(), LAW_NAME, max_versions=300)
    assert result.status == "ok"
    assert calls == [1, 2]
    assert result.total_count == 188
    assert result.collected_item_count == 188
    assert result.exact_match_count == 188
    assert result.distinct_mst_count == 188


def test_phase42_deduplicates_mst_across_pages(monkeypatch):
    _enable(monkeypatch)
    pages = {
        1: _search_xml(1, 3, 2, [_law_xml("1", effective="20250101"), _law_xml("2", effective="20250201")]),
        2: _search_xml(2, 3, 2, [_law_xml("2", effective="20250301")]),
    }
    _mock_pages(monkeypatch, pages)
    result = discover_law_versions(_client(), LAW_NAME, max_versions=10)
    assert [item.mst for item in result.versions] == ["2", "1"]
    assert "duplicate_mst:2" in result.warnings


def test_phase42_exact_law_name_filter_and_cdata_whitespace_normalization():
    payload = {"LawSearch": {"resultCode": "00", "law": [
        {"법령명한글": " Phase42 Live Law ", "법령일련번호": "1", "시행일자": "20250101"},
        {"법령명한글": "Phase42 Live Law Enforcement Decree", "법령일련번호": "2", "시행일자": "20260101"},
        {"법령명한글": "Special Phase42 Live Law", "법령일련번호": "3", "시행일자": "20270101"},
    ]}}
    versions = select_exact_law_versions(parse_eflaw_list_response(payload)["laws"], LAW_NAME)
    assert [item.mst for item in versions] == ["1"]
    assert normalize_law_name("  Phase42   Live Law  ") == normalize_law_name("Phase42 Live Law")
    xml = _search_xml(1, 1, 1, ["<law><법령명한글><![CDATA[ Phase42 Live Law ]]></법령명한글><법령일련번호>9</법령일련번호></law>"])
    parsed = parse_eflaw_list_response(parse_response(_xml_response("https://example.invalid", xml)).payload)
    assert select_exact_law_versions(parsed["laws"], LAW_NAME)[0].mst == "9"


def test_phase42_sorting_uses_effective_promulgation_then_mst_and_selects_latest_pair():
    items = [
        normalize_law_version({"law_name": LAW_NAME, "mst": "10", "effective_date": "20250101", "promulgation_date": "20240101"}, LAW_NAME),
        normalize_law_version({"law_name": LAW_NAME, "mst": "11", "effective_date": "20260101", "promulgation_date": "20240101"}, LAW_NAME),
        normalize_law_version({"law_name": LAW_NAME, "mst": "12", "effective_date": "20260101", "promulgation_date": "20250101"}, LAW_NAME),
        normalize_law_version({"law_name": LAW_NAME, "mst": "13", "effective_date": "20260101", "promulgation_date": "20250101"}, LAW_NAME),
    ]
    versions = sort_law_versions([item for item in items if item is not None])
    assert [item.mst for item in versions] == ["13", "12", "11", "10"]
    pair = select_latest_version_pair(versions, LAW_NAME)
    assert pair is not None
    assert pair.from_mst == "12"
    assert pair.to_mst == "13"


def test_phase42_no_previous_version_returns_none():
    version = normalize_law_version({"law_name": LAW_NAME, "mst": "1", "effective_date": "20260101"}, LAW_NAME)
    assert version is not None
    assert select_latest_version_pair([version], LAW_NAME) is None


def test_phase42_api_result_code_error_and_empty_intermediate_page(monkeypatch):
    _enable(monkeypatch)
    _mock_pages(monkeypatch, {1: _search_xml(1, 1, 100, [], result_code="99")})
    assert discover_law_versions(_client(), LAW_NAME).status == "source_error"
    pages = {1: _search_xml(1, 188, 100, [_law_xml("1")]), 2: _search_xml(2, 188, 100, [])}
    _mock_pages(monkeypatch, pages)
    result = discover_law_versions(_client(), LAW_NAME)
    assert result.status == "source_error"
    assert "empty_intermediate_page" in result.errors


def test_phase42_secret_not_exposed_in_discovery(monkeypatch):
    _enable(monkeypatch)
    _mock_pages(monkeypatch, {1: _search_xml(1, 1, 100, [_law_xml("1")])})
    result = discover_law_versions(_client(), LAW_NAME)
    dumped = json.dumps(result.to_dict(), ensure_ascii=False, default=str)
    assert SECRET not in dumped
    assert "REDACTED" in dumped
    assert result.secret_exposed is False


def test_phase42_endpoint_normal_response_and_manual_validation(monkeypatch):
    _cleanup()
    try:
        _fixture_docs()
        _enable(monkeypatch)
        pages = {1: _search_xml(1, 2, 100, [_law_xml(FROM_MST, effective="20250101", promulgation="20240101"), _law_xml(TO_MST, effective="20260101", promulgation="20250101")])}
        _mock_pages(monkeypatch, pages)
        response = client.post("/api/law-updates/live-impact", json={"law_name": LAW_NAME})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["source"] == "MOLEG"
        assert data["from_version"]["mst"] == FROM_MST
        assert data["to_version"]["mst"] == TO_MST
        assert data["changed"] is True
        assert data["discovery"]["requested_pages"] == [1]
        assert SECRET not in json.dumps(data, ensure_ascii=False)
        same = client.post("/api/law-updates/live-impact", json={"law_name": LAW_NAME, "from_mst": FROM_MST, "to_mst": FROM_MST})
        assert same.status_code == 400
        reverse = client.post("/api/law-updates/live-impact", json={"law_name": LAW_NAME, "from_mst": TO_MST, "to_mst": FROM_MST})
        assert reverse.status_code == 400
    finally:
        _cleanup()


def test_phase42_validate_same_and_reverse_mst_inputs():
    older = normalize_law_version({"law_name": LAW_NAME, "mst": FROM_MST, "effective_date": "20250101"}, LAW_NAME)
    newer = normalize_law_version({"law_name": LAW_NAME, "mst": TO_MST, "effective_date": "20260101"}, LAW_NAME)
    assert older is not None and newer is not None
    _, same_error = validate_version_pair([older, newer], FROM_MST, FROM_MST)
    _, reverse_error = validate_version_pair([older, newer], TO_MST, FROM_MST)
    assert same_error == "same_mst_not_comparable"
    assert reverse_error == "from_mst_newer_than_to_mst"




def test_phase42_parser_reads_total_page_and_num_of_rows():
    parsed = parse_eflaw_list_response({"LawSearch": {"resultCode": "00", "totalCnt": "188", "page": "2", "numOfRows": "100", "law": []}})
    assert parsed["total_cnt"] == 188
    assert parsed["page"] == 2
    assert parsed["num_of_rows"] == 100


def test_phase42_missing_mst_records_warning_without_stopping():
    result = discover_result = type("Result", (), {"warnings": [], "response_content_hash": None, "result_code": "00", "result_message": "success"})()
    assert normalize_law_version({"law_name": LAW_NAME, "mst": None}, LAW_NAME, result=discover_result) is None
    assert "missing_mst" in result.warnings


def test_phase42_invalid_mst_records_warning_but_keeps_version():
    result = type("Result", (), {"warnings": [], "response_content_hash": None, "result_code": "00", "result_message": "success"})()
    version = normalize_law_version({"law_name": LAW_NAME, "mst": "bad-mst", "effective_date": "20250101"}, LAW_NAME, result=result)
    assert version is not None
    assert version.mst == "bad-mst"
    assert "invalid_mst:bad-mst" in result.warnings


def test_phase42_empty_first_page_is_no_versions(monkeypatch):
    _enable(monkeypatch)
    _mock_pages(monkeypatch, {1: _search_xml(1, 0, 100, [])})
    result = discover_law_versions(_client(), LAW_NAME)
    assert result.status == "no_versions"
    assert result.versions == []


def test_phase42_manual_pair_not_found_in_discovery_allows_unverified_order_when_not_reversed():
    older = normalize_law_version({"law_name": LAW_NAME, "mst": "100", "effective_date": "20250101"}, LAW_NAME)
    assert older is not None
    selection, error = validate_version_pair([older], "101", "102")
    assert selection is None
    assert error is None


def test_phase42_single_manual_mst_is_invalid_request(monkeypatch):
    _enable(monkeypatch)
    _mock_pages(monkeypatch, {1: _search_xml(1, 1, 100, [_law_xml(FROM_MST, effective="20250101")])})
    response = client.post("/api/law-updates/live-impact", json={"law_name": LAW_NAME, "from_mst": FROM_MST})
    assert response.status_code == 400
    assert response.json()["detail"]["errors"] == ["from_mst_and_to_mst_required_together"]
