from __future__ import annotations

import json
import os
import subprocess
import sys

import httpx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.moleg_live_client import (
    BROWSER_SUCCESS_EXPECTED_LAWS,
    DEFAULT_ACCEPT,
    DEFAULT_USER_AGENT,
    MOLEG_LAW_SEARCH_PATH,
    MOLEG_LAW_SERVICE_PATH,
    MolegLiveClient,
    parse_response,
)
from app.services.moleg_probe_service import run_moleg_live_probes

client = TestClient(app)
SECRET = "TEST_PHASE36_SECRET_DO_NOT_USE"

SEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
  <target>law</target>
  <키워드><![CDATA[도시개발법]]></키워드>
  <totalCnt>3</totalCnt>
  <page>1</page>
  <numOfRows>3</numOfRows>
  <resultCode>00</resultCode>
  <resultMsg>success</resultMsg>
  <law>
    <법령명한글><![CDATA[도시개발법]]></법령명한글>
    <법령일련번호>284059</법령일련번호>
    <법령ID>002024</법령ID>
    <공포일자>20260305</공포일자>
    <공포번호>21447</공포번호>
    <제개정구분명>타법개정</제개정구분명>
    <소관부처명>국토교통부</소관부처명>
    <법령구분명>법률</법령구분명>
    <시행일자>20260701</시행일자>
    <법령상세링크>/DRF/lawService.do?OC=TEST_PHASE36_SECRET_DO_NOT_USE&amp;target=law&amp;MST=284059&amp;type=HTML&amp;efYd=20260701</법령상세링크>
  </law>
  <law>
    <법령명한글><![CDATA[도시개발법 시행령]]></법령명한글>
    <법령일련번호>287279</법령일련번호>
    <법령ID>003421</법령ID>
    <법령구분명>대통령령</법령구분명>
    <소관부처명>국토교통부</소관부처명>
    <시행일자>20260701</시행일자>
  </law>
  <law>
    <법령명한글><![CDATA[도시개발법 시행규칙]]></법령명한글>
    <법령일련번호>268933</법령일련번호>
    <법령ID>007096</법령ID>
    <법령구분명>국토교통부령</법령구분명>
    <소관부처명>국토교통부</소관부처명>
    <시행일자>20250131</시행일자>
  </law>
</LawSearch>
"""

DETAIL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Law>
  <법령명한글>Dummy Detail Law</법령명한글>
  <조문>
    <조문번호>DUMMY-ARTICLE</조문번호>
    <조문제목>Dummy Article Title For Parser Fixture</조문제목>
  </조문>
</Law>
"""


def _clear_settings() -> None:
    get_settings.cache_clear()


def _enable_live(monkeypatch, base_url: str = "https://www.law.go.kr") -> None:
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", base_url)
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    _clear_settings()


def _xml_response(url: str, text: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, text=text, headers={"content-type": "application/xml"}, request=httpx.Request("GET", url))


def test_phase36_browser_success_xml_parser_and_redaction():
    response = _xml_response("http://www.law.go.kr/DRF/lawSearch.do", SEARCH_XML)
    parsed = parse_response(response)

    assert parsed.response_format == "xml"
    assert parsed.sample_law_count == 3
    assert parsed.first_law_identifier == "284059"
    assert parsed.law_search is not None
    assert parsed.law_search["result_code"] == "00"
    assert parsed.law_search["total_cnt"] == 3
    assert [item["law_name"] for item in parsed.law_search["laws"]] == [item["law_name"] for item in BROWSER_SUCCESS_EXPECTED_LAWS]
    assert parsed.law_search["laws"][0]["law_id"] == "002024"
    dumped = json.dumps(parsed.law_search, ensure_ascii=False)
    assert SECRET not in dumped
    assert "OC=[REDACTED]" in dumped


def test_phase36_api_error_result_code_is_classified():
    response = _xml_response("http://www.law.go.kr/DRF/lawSearch.do", "<LawSearch><resultCode>99</resultCode><resultMsg>error</resultMsg></LawSearch>")
    diagnostic = MolegLiveClient(base_url="http://www.law.go.kr", api_key=SECRET, retry_count=0)
    diagnostic.live_test_enabled = True

    def fake_get(url, params, **kwargs):
        return response

    original = httpx.get
    httpx.get = fake_get
    try:
        assert diagnostic.diagnose_law_search().reason_type == "api_error_response"
    finally:
        httpx.get = original


def test_phase36_endpoint_matrix_selects_http_and_sanitizes(monkeypatch):
    _enable_live(monkeypatch)

    def fake_get(url, params, **kwargs):
        assert kwargs["headers"]["User-Agent"] == DEFAULT_USER_AGENT
        assert kwargs["headers"]["Accept"] == DEFAULT_ACCEPT
        assert params["OC"] == SECRET
        if url.startswith("http://"):
            return _xml_response(url, SEARCH_XML)
        raise httpx.ConnectError("connection refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        result = run_moleg_live_probes(probe="matrix")
    finally:
        _clear_settings()

    assert result.final_reason_type == "ok"
    assert result.selected_endpoint == "http://www.law.go.kr"
    assert result.endpoint_matrix[0]["selected_candidate"] is True
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert SECRET not in dumped
    assert "OC=%5BREDACTED%5D" in dumped or "OC=[REDACTED]" in dumped


def test_phase36_search_detail_parse_ready_for_live_ingest(monkeypatch):
    _enable_live(monkeypatch)
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get(url, params, **kwargs):
        calls.append((url, dict(params)))
        if MOLEG_LAW_SEARCH_PATH in url:
            return _xml_response(url, SEARCH_XML)
        if MOLEG_LAW_SERVICE_PATH in url:
            assert params["MST"] in {"284059", "287279", "268933"}
            assert params["type"] == "XML"
            return _xml_response(url, DETAIL_XML)
        raise AssertionError(url)

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        result = run_moleg_live_probes(probe="all")
    finally:
        _clear_settings()

    assert result.search_ok is True
    assert result.detail_ok is True
    assert result.parse_ok is True
    assert result.ready_for_live_ingest is True
    assert result.final_reason_type == "ok"
    assert result.parse_probe is not None
    assert result.parse_probe.sanitized_detail["parsed_article_count"] == 1
    assert result.raw_payload_stored is False
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert SECRET not in dumped
    assert "Dummy Article Title" not in dumped


def test_phase36_detail_probe_builds_mst_and_efyd_query(monkeypatch):
    _enable_live(monkeypatch, base_url="http://www.law.go.kr")
    seen: dict[str, str] = {}

    def fake_get(url, params, **kwargs):
        seen.update(params)
        return _xml_response(url, DETAIL_XML)

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        result = run_moleg_live_probes(probe="detail", mst="284059", ef_yd="20260701")
    finally:
        _clear_settings()

    assert result.detail_ok is True
    assert seen["MST"] == "284059"
    assert seen["efYd"] == "20260701"
    assert seen["OC"] == SECRET
    assert result.secret_exposed is False


def test_phase36_ready_for_live_ingest_false_when_parse_skipped(monkeypatch):
    _enable_live(monkeypatch, base_url="http://www.law.go.kr")

    def fake_get(url, params, **kwargs):
        if MOLEG_LAW_SEARCH_PATH in url:
            return _xml_response(url, SEARCH_XML)
        raise httpx.ConnectError("connection refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        result = run_moleg_live_probes(probe="all")
    finally:
        _clear_settings()

    assert result.search_ok is True
    assert result.detail_ok is False
    assert result.parse_ok is False
    assert result.ready_for_live_ingest is False
    assert result.final_reason_type == "connection_refused"


def test_phase36_smoke_script_matrix_option_without_live_network():
    env = {**os.environ, "MOLEG_LIVE_TEST_ENABLED": "false"}
    completed = subprocess.run([sys.executable, "-m", "scripts.smoke_moleg_transport", "--probe", "matrix"], capture_output=True, text=True, check=False, env=env)
    assert completed.returncode == 0
    data = json.loads(completed.stdout)
    assert data["probe"] == "matrix"
    assert "endpoint_matrix" in data
    assert data["secret_exposed"] is False
    assert data["raw_payload_stored"] is False


def test_phase36_diagnostic_snapshot_and_analyze_include_browser_metadata(monkeypatch):
    _enable_live(monkeypatch, base_url="http://www.law.go.kr")

    def fake_get(url, params, **kwargs):
        if MOLEG_LAW_SEARCH_PATH in url:
            return _xml_response(url, SEARCH_XML)
        return _xml_response(url, DETAIL_XML)

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        diagnostic = client.get("/api/legal-references/moleg/diagnostic")
        assert diagnostic.status_code == 200
        diagnostic_data = diagnostic.json()
        assert diagnostic_data["browser_success_metadata_present"] is True
        assert diagnostic_data["ready_for_live_ingest"] is True
        assert diagnostic_data["selected_endpoint"] == "http://www.law.go.kr"
        assert diagnostic_data["secret_exposed"] is False

        snapshot = client.get("/api/legal-references/official-law-snapshot")
        assert snapshot.status_code == 200
        snapshot_data = snapshot.json()
        assert snapshot_data["moleg_browser_success_metadata_present"] is True
        assert snapshot_data["moleg_ready_for_live_ingest"] is True
        assert snapshot_data["secret_exposed"] is False

        response = client.post(
            "/api/analyze",
            json={
                "project_name": "Phase36 Analyze Smoke",
                "location": "Test Location",
                "area_square_meters": 100000,
                "implementation_method": "expropriation_or_use",
                "implementer_type": "public",
                "local_government": "Test LG",
            },
        )
        assert response.status_code == 200
        assert len(response.json()["procedures"]) == 13
    finally:
        _clear_settings()
