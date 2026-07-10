import json
import os
import subprocess
import sys

import httpx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.moleg_diagnostic_service import diagnose_moleg_safe
from app.services.moleg_live_client import MolegLiveClient

client = TestClient(app)
SECRET = "TEST_PHASE31_SECRET_DO_NOT_USE"


def _clear_settings():
    get_settings.cache_clear()


def test_phase31_env_not_configured_diagnostic(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    _clear_settings()
    try:
        result = diagnose_moleg_safe()
        assert result.reason_type == "not_configured"
        assert result.configured is False
        assert result.secret_exposed is False
        assert result.raw_payload_stored is False
        assert result.fallback_available is True
    finally:
        _clear_settings()


def test_phase31_live_disabled_diagnostic(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "false")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    _clear_settings()
    try:
        result = diagnose_moleg_safe()
        assert result.reason_type == "live_disabled"
        assert result.live_enabled is False
        assert result.configured is True
    finally:
        _clear_settings()


def test_phase31_invalid_base_url_diagnostic():
    diagnostic = MolegLiveClient(base_url="law.go.kr", api_key=SECRET, timeout_seconds=1, retry_count=0)
    diagnostic.live_test_enabled = True

    result = diagnostic.diagnose_law_search()

    assert result.reason_type == "invalid_base_url"


def test_phase31_timeout_invalid_format_and_api_error(monkeypatch):
    def timeout_get(url, params, timeout):
        raise httpx.TimeoutException("timed out", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", timeout_get)
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1, retry_count=0)
    diagnostic.live_test_enabled = True
    assert diagnostic.diagnose_law_search().reason_type == "connection_timeout"

    def html_get(url, params, timeout):
        return httpx.Response(200, text="<html>error</html>", headers={"content-type": "text/html"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", html_get)
    assert diagnostic.diagnose_law_search().reason_type == "invalid_response_format"

    def api_error_get(url, params, timeout):
        return httpx.Response(200, json={"errorCode": "E001", "message": "denied"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", api_error_get)
    assert diagnostic.diagnose_law_search().reason_type == "api_error_response"


def test_phase31_parsing_error_and_secret_redaction(monkeypatch):
    def broken_json_get(url, params, timeout):
        return httpx.Response(200, text='{bad json', headers={"content-type": "application/json"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", broken_json_get)
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1, retry_count=0)
    diagnostic.live_test_enabled = True
    result = diagnostic.diagnose_law_search()
    dumped = str(result.model_dump())
    assert result.reason_type == "parsing_error"
    assert SECRET not in dumped
    assert result.secret_exposed is False
    assert result.raw_payload_stored is False


def test_phase31_safe_endpoint_and_snapshot_include_moleg_status(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "false")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    _clear_settings()
    try:
        diagnostic = client.get("/api/legal-references/moleg/diagnostic")
        assert diagnostic.status_code == 200
        diagnostic_data = diagnostic.json()
        assert diagnostic_data["reason_type"] == "live_disabled"
        assert diagnostic_data["secret_exposed"] is False
        assert diagnostic_data["raw_payload_stored"] is False
        assert SECRET not in json.dumps(diagnostic_data, ensure_ascii=False)

        snapshot = client.get("/api/legal-references/official-law-snapshot")
        assert snapshot.status_code == 200
        snapshot_data = snapshot.json()
        assert snapshot_data["moleg_reason_type"] == "live_disabled"
        assert snapshot_data["moleg_secret_exposed"] is False
        assert snapshot_data["moleg_raw_payload_stored"] is False
        assert snapshot_data["fallback_available"] is True
    finally:
        _clear_settings()


def test_phase31_analyze_procedure_count_is_independent_from_moleg_failure(monkeypatch):
    def failing_get(url, params, timeout):
        raise httpx.ConnectError("connection refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", failing_get)
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "Phase31 Analyze Smoke",
            "location": "Seongnam-si, Gyeonggi-do",
            "area_square_meters": 100000,
            "implementation_method": "expropriation_or_use",
            "implementer_type": "public",
            "local_government": "Seongnam-si",
        },
    )
    assert response.status_code == 200
    assert len(response.json()["procedures"]) == 13


def test_phase31_smoke_script_runs_without_live_config():
    env = {**os.environ, "MOLEG_LIVE_TEST_ENABLED": "false"}
    completed = subprocess.run([sys.executable, "-m", "scripts.smoke_moleg_transport"], capture_output=True, text=True, check=False, env=env)
    assert completed.returncode == 0
    data = json.loads(completed.stdout)
    assert data["secret_exposed"] is False
    assert data["raw_payload_stored"] is False
    assert data["reason_type"] in {
        "live_disabled",
        "not_configured",
        "invalid_base_url",
        "dns_error",
        "connection_timeout",
        "connection_refused",
        "tls_error",
        "http_error_status",
        "invalid_response_format",
        "api_error_response",
        "parsing_error",
        "unknown_connection_error",
        "ok",
    }
