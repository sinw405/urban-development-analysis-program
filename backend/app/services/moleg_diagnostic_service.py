from __future__ import annotations

from app.schemas.official_law_source import MolegDiagnosticResult, MolegLiveDiagnosticResult
from app.services.moleg_live_client import MolegLiveClient


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


def diagnose_moleg_live_only(query: str = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95") -> MolegLiveDiagnosticResult:
    return MolegLiveClient().diagnose_law_search(query=query)


def _legacy_reason_type(reason_type: str) -> str:
    if reason_type in {"dns_error", "ssl_error", "proxy_error", "connection_refused", "unknown_connection_error", "invalid_response", "validation_error"}:
        return "connection_error"
    return reason_type
