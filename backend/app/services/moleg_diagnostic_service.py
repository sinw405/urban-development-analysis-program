from __future__ import annotations

from app.schemas.official_law_source import MolegDiagnosticResult, MolegLiveDiagnosticResult, MolegSafeDiagnosticResponse
from app.services.moleg_live_client import DEFAULT_LIVE_QUERY, MolegLiveClient
from app.services.moleg_probe_service import run_moleg_live_probes


def diagnose_moleg_connectivity() -> MolegDiagnosticResult:
    live_result = diagnose_moleg_live_only()
    return MolegDiagnosticResult(
        live_configured=live_result.live_configured,
        has_secret=live_result.has_secret,
        base_url=live_result.sanitized_base_url,
        endpoint=live_result.sanitized_endpoint,
        result=live_result.result,
        reason_type=_legacy_reason_type(live_result.reason_type),
        secret_exposed=live_result.secret_exposed,
    )


def diagnose_moleg_live_only(query: str = DEFAULT_LIVE_QUERY) -> MolegLiveDiagnosticResult:
    return MolegLiveClient().diagnose_law_search(query=query)


def diagnose_moleg_safe(query: str = DEFAULT_LIVE_QUERY) -> MolegSafeDiagnosticResponse:
    return run_moleg_live_probes(probe="all", query=query)


def _legacy_reason_type(reason_type: str) -> str:
    if reason_type in {
        "dns_error",
        "connection_timeout",
        "connection_refused",
        "tls_error",
        "proxy_error",
        "unknown_connection_error",
        "invalid_base_url",
        "invalid_response_format",
        "empty_response",
        "html_error_response",
        "parsing_error",
    }:
        return "connection_error"
    if reason_type == "live_disabled":
        return "disabled"
    if reason_type == "http_error_status":
        return "http_error"
    return reason_type