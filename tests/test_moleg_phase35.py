from __future__ import annotations

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
from app.services.moleg_probe_service import run_moleg_live_probes

client = TestClient(app)
SECRET = "TEST_PHASE35_SECRET_DO_NOT_USE"


def _clear_settings() -> None:
    get_settings.cache_clear()


def test_phase35_config_probe_not_configured_and_live_disabled(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "true")
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    _clear_settings()
    try:
        result = run_moleg_live_probes(probe="config")
        assert result.final_reason_type == "not_configured"
        assert result.config_probe is not None
        assert result.config_probe.sanitized_detail["key_present"] is False
    finally:
        _clear_settings()

    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "false")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    _clear_settings()
    try:
        result = run_moleg_live_probes(probe="config")
        assert result.final_reason_type == "live_disabled"
        assert SECRET not in json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    finally:
        _clear_settings()


def test_phase35_invalid_base_url_and_transport_exception_taxonomy():
    client_obj = MolegLiveClient(base_url="law.go.kr", api_key=SECRET, timeout_seconds=1, retry_count=0)
    client_obj.live_test_enabled = True
    assert client_obj.diagnose_law_search().reason_type == "invalid_base_url"


def test_phase35_response_reason_taxonomy(monkeypatch):
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1, retry_count=0)
    diagnostic.live_test_enabled = True

    def empty_get(url, params, timeout):
        return httpx.Response(200, text="", headers={"content-type": "application/json"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", empty_get)
    assert diagnostic.diagnose_law_search().reason_type == "empty_response"

    def html_get(url, params, timeout):
        return httpx.Response(200, text="<html>blocked</html>", headers={"content-type": "text/html"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", html_get)
    assert diagnostic.diagnose_law_search().reason_type == "html_error_response"

    def unauthorized_get(url, params, timeout):
        return httpx.Response(403, text="denied", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", unauthorized_get)
    assert diagnostic.diagnose_law_search().reason_type == "unauthorized_or_invalid_key"

    def invalid_param_get(url, params, timeout):
        return httpx.Response(400, text="bad request", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", invalid_param_get)
    assert diagnostic.diagnose_law_search().reason_type == "invalid_request_parameter"

    def api_error_get(url, params, timeout):
        return httpx.Response(200, json={"LawSearch": {"errorCode": "E001", "errorMessage": "invalid parameter"}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", api_error_get)
    assert diagnostic.diagnose_law_search().reason_type in {"api_error_response", "invalid_request_parameter", "unauthorized_or_invalid_key"}


def test_phase35_exception_taxonomy(monkeypatch):
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1, retry_count=0)
    diagnostic.live_test_enabled = True

    def proxy_get(url, params, timeout):
        raise httpx.ProxyError("proxy failed", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", proxy_get)
    assert diagnostic.diagnose_law_search().reason_type == "proxy_error"

    def tls_get(url, params, timeout):
        raise httpx.ConnectError("certificate verify failed", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", tls_get)
    assert diagnostic.diagnose_law_search().reason_type == "tls_error"

    def dns_get(url, params, timeout):
        raise httpx.ConnectError("getaddrinfo failed", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", dns_get)
    assert diagnostic.diagnose_law_search().reason_type == "dns_error"


def test_phase35_secret_and_query_redaction(monkeypatch):
    def ok_get(url, params, timeout):
        assert params["OC"] == SECRET
        return httpx.Response(200, json={"LawSearch": {"law": [{"MST": "DUMMY-MST", "법령명한글": "Dummy Law"}]}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", ok_get)
    diagnostic = MolegLiveClient(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=1, retry_count=0)
    diagnostic.live_test_enabled = True
    result = diagnostic.diagnose_law_search(query="Dummy Law")
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert result.reason_type == "ok"
    assert SECRET not in dumped
    assert "OC=%5BREDACTED%5D" in dumped or "OC=[REDACTED]" in dumped
    assert result.raw_payload_stored is False
    assert result.secret_exposed is False


def test_phase35_smoke_script_probe_options(monkeypatch):
    env = {**os.environ, "MOLEG_LIVE_TEST_ENABLED": "false"}
    completed = subprocess.run([sys.executable, "-m", "scripts.smoke_moleg_transport", "--probe", "config"], capture_output=True, text=True, check=False, env=env)
    assert completed.returncode == 0
    data = json.loads(completed.stdout)
    assert data["probe"] == "config"
    assert data["secret_exposed"] is False
    assert data["raw_payload_stored"] is False
    assert "final_reason_type" in data


def test_phase35_diagnostic_endpoint_snapshot_and_analyze(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_LIVE_TEST_ENABLED", "false")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://www.law.go.kr")
    monkeypatch.setenv("MOLEG_API_KEY", SECRET)
    _clear_settings()
    try:
        diagnostic = client.get("/api/legal-references/moleg/diagnostic")
        assert diagnostic.status_code == 200
        diagnostic_data = diagnostic.json()
        assert diagnostic_data["final_reason_type"] == "live_disabled"
        assert diagnostic_data["config_probe"]["reason_type"] == "live_disabled"
        assert diagnostic_data["secret_exposed"] is False
        assert SECRET not in json.dumps(diagnostic_data, ensure_ascii=False)

        snapshot = client.get("/api/legal-references/official-law-snapshot")
        assert snapshot.status_code == 200
        snapshot_data = snapshot.json()
        assert snapshot_data["moleg_final_reason_type"] == "live_disabled"
        assert snapshot_data["moleg_search_ok"] is False
        assert snapshot_data["moleg_parse_ok"] is False
        assert snapshot_data["secret_exposed"] is False

        response = client.post(
            "/api/analyze",
            json={
                "project_name": "Phase35 Analyze Smoke",
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