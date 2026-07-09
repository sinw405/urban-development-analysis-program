import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.moleg_live_client import MolegLiveClient, SECRET_REDACTION
from tests.test_official_law_source_phase25 import _cleanup, _create_reference, _ingest_fixture

client = TestClient(app)
SECRET = "TEST_PHASE26_SECRET_DO_NOT_USE"


def test_live_diagnostic_without_secret_is_not_configured():
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key="", timeout_seconds=1)
    diagnostic.live_test_enabled = True

    result = diagnostic.diagnose_law_search()

    assert result.live_configured is False
    assert result.has_secret is False
    assert result.secret_exposed is False
    assert result.reason_type == "disabled"
    assert SECRET not in str(result.model_dump())


def test_live_diagnostic_sanitizes_final_url_and_response_preview(monkeypatch):
    def fake_get(url, params, timeout):
        assert params["OC"] == SECRET
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"LawSearch": {"OC": SECRET, "law": []}},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr/", api_key=SECRET, timeout_seconds=3)
    diagnostic.live_test_enabled = True

    result = diagnostic.diagnose_law_search()
    dumped = str(result.model_dump())

    assert result.result == "ok"
    assert result.reason_type == "ok"
    assert result.final_url_sanitized is not None
    assert "OC=%5BREDACTED%5D" in result.final_url_sanitized or "OC=[REDACTED]" in result.final_url_sanitized
    assert SECRET not in dumped
    assert SECRET_REDACTION in dumped
    assert result.secret_exposed is False
    assert result.query_keys == ["OC", "display", "page", "query", "target", "type"]


def test_live_diagnostic_classifies_dns_error_without_500(monkeypatch):
    def fake_get(url, params, timeout):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("getaddrinfo failed", request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1)
    diagnostic.live_test_enabled = True

    result = diagnostic.diagnose_law_search()

    assert result.result == "source_error"
    assert result.reason_type == "dns_error"
    assert result.error_class == "ConnectError"
    assert result.status_code is None
    assert result.secret_exposed is False
    assert SECRET not in str(result.model_dump())


def test_live_diagnostic_classifies_timeout(monkeypatch):
    def fake_get(url, params, timeout):
        request = httpx.Request("GET", url)
        raise httpx.TimeoutException("timed out", request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1)
    diagnostic.live_test_enabled = True

    result = diagnostic.diagnose_law_search()

    assert result.reason_type == "timeout"
    assert result.result == "source_error"
    assert result.secret_exposed is False


def test_live_diagnostic_classifies_invalid_response(monkeypatch):
    def fake_get(url, params, timeout):
        return httpx.Response(200, text="not-json-or-xml", headers={"content-type": "text/plain"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1)
    diagnostic.live_test_enabled = True

    result = diagnostic.diagnose_law_search()

    assert result.reason_type == "invalid_response"
    assert result.response_preview_sanitized == "not-json-or-xml"
    assert result.secret_exposed is False


def test_live_diagnostic_endpoint_returns_safe_shape(monkeypatch):
    def fake_get(url, params, timeout):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    response = client.get("/api/legal-references/moleg-live-diagnostic")

    assert response.status_code == 200
    data = response.json()
    assert data["secret_exposed"] is False
    assert "sanitized_endpoint" in data
    assert "query_keys" in data
    assert "error_message_sanitized" in data


def test_db_first_verify_preview_still_wins_when_live_diagnostic_fails(monkeypatch):
    def fake_get(url, params, timeout):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    _cleanup()
    try:
        document_id = _ingest_fixture()
        reference_id = _create_reference()

        response = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [reference_id], "source_mode": "live"})

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_mode"] == "official_db"
        assert item["document_id"] == document_id
        assert item["source_error"] is False
    finally:
        _cleanup()


def test_mock_fallback_without_db_snapshot_is_preserved(monkeypatch):
    def fake_get(url, params, timeout):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    _cleanup()
    try:
        reference_id = _create_reference(
            law_name="TEST_LAW_DO_NOT_USE",
            article_no="TEST_ARTICLE_DO_NOT_USE",
            article_title="TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
        )

        response = client.post("/api/legal-references/verify-preview", json={"procedure_reference_ids": [reference_id], "source_mode": "live"})

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_mode"] == "fallback"
        assert item["match_status"] == "matched"
        assert item["source_error"] is True
        assert item["reason_type"] == "source_error"
    finally:
        _cleanup()
