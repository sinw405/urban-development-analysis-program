from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas.official_law_source import MolegDiagnosticResult, MolegLiveDiagnosticResult, MolegSafeDiagnosticResponse
from app.services.moleg_live_client import FALLBACK_SOURCE_MODES, MolegLiveClient, reason_message


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


def diagnose_moleg_live_only(query: str = "도시개발법") -> MolegLiveDiagnosticResult:
    return MolegLiveClient().diagnose_law_search(query=query)


def diagnose_moleg_safe(query: str = "도시개발법") -> MolegSafeDiagnosticResponse:
    live_result = diagnose_moleg_live_only(query=query)
    diagnostic_detail: dict[str, Any] = {
        "configured": live_result.configured,
        "key_present": live_result.key_present,
        "key_length": live_result.key_length,
        "key_fingerprint": live_result.key_fingerprint,
        "base_url_configured": live_result.base_url_configured,
        "sanitized_base_url": live_result.sanitized_base_url,
        "sanitized_endpoint": live_result.sanitized_endpoint,
        "query_keys": live_result.query_keys,
        "allowed_env_names": live_result.allowed_env_names,
        "configured_env_names": live_result.configured_env_names,
        "timeout_seconds": live_result.timeout_seconds,
        "retry_count": live_result.retry_count,
        "backoff_seconds": live_result.backoff_seconds,
        "status_code": live_result.status_code,
        "elapsed_ms": live_result.elapsed_ms,
        "error_class": live_result.error_class,
        "error_message_sanitized": live_result.error_message_sanitized,
        "response_content_type": live_result.response_content_type,
    }
    return MolegSafeDiagnosticResponse(
        live_enabled=live_result.live_enabled,
        configured=live_result.configured,
        transport_ok=live_result.reason_type == "ok",
        reason_type=live_result.reason_type,
        reason_message=live_result.reason_message or reason_message(live_result.reason_type),
        diagnostic_detail=diagnostic_detail,
        next_action=live_result.suggested_next_action,
        secret_exposed=False,
        raw_payload_stored=False,
        request_sanitized=True,
        fallback_available=True,
        fallback_source_modes=FALLBACK_SOURCE_MODES,
        checked_at=datetime.now(UTC),
        response_format=live_result.response_format,
        sample_law_count=live_result.sample_law_count,
    )


def _legacy_reason_type(reason_type: str) -> str:
    if reason_type in {
        "dns_error",
        "connection_timeout",
        "connection_refused",
        "tls_error",
        "unknown_connection_error",
        "invalid_base_url",
        "invalid_response_format",
        "parsing_error",
    }:
        return "connection_error"
    if reason_type == "live_disabled":
        return "disabled"
    if reason_type == "http_error_status":
        return "http_error"
    return reason_type
