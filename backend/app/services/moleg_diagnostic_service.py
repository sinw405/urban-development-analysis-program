from __future__ import annotations

from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import MolegDiagnosticResult
from app.services.official_law_source import MOLEG_LAW_SEARCH_PATH


REASON_TIMEOUT = "timeout"
REASON_CONNECTION_ERROR = "connection_error"
REASON_HTTP_ERROR = "http_error"
REASON_PARSE_ERROR = "parse_error"
REASON_AUTH_ERROR = "auth_error"
REASON_DISABLED = "disabled"
REASON_UNKNOWN = "unknown"


def diagnose_moleg_connectivity() -> MolegDiagnosticResult:
    settings = get_settings()
    endpoint = MOLEG_LAW_SEARCH_PATH
    has_secret = bool(settings.moleg_api_key)
    live_configured = settings.moleg_live_test_configured
    sanitized_base_url = settings.moleg_api_base_url.split("?", 1)[0].rstrip("/") or None

    if not settings.moleg_live_test_enabled:
        return MolegDiagnosticResult(
            live_configured=live_configured,
            has_secret=has_secret,
            base_url=sanitized_base_url,
            endpoint=endpoint,
            result="skipped",
            reason_type=REASON_DISABLED,
        )
    if not settings.moleg_api_configured:
        return MolegDiagnosticResult(
            live_configured=live_configured,
            has_secret=has_secret,
            base_url=sanitized_base_url,
            endpoint=endpoint,
            result="source_unavailable",
            reason_type=REASON_AUTH_ERROR if not has_secret else REASON_DISABLED,
        )

    try:
        response = httpx.get(
            urljoin(f"{sanitized_base_url}/", endpoint.lstrip("/")),
            params={"target": "law", "type": "JSON", "query": "healthcheck", "OC": settings.moleg_api_key},
            timeout=settings.moleg_api_timeout_seconds,
        )
        if response.status_code in {401, 403}:
            reason = REASON_AUTH_ERROR
        elif response.status_code >= 400:
            reason = REASON_HTTP_ERROR
        else:
            reason = _response_reason(response)
        return MolegDiagnosticResult(
            live_configured=live_configured,
            has_secret=has_secret,
            base_url=sanitized_base_url,
            endpoint=endpoint,
            result="ok" if reason == "ok" else "source_error",
            reason_type=reason,
        )
    except httpx.TimeoutException:
        reason = REASON_TIMEOUT
    except httpx.ConnectError:
        reason = REASON_CONNECTION_ERROR
    except httpx.HTTPError:
        reason = REASON_HTTP_ERROR
    except Exception:
        reason = REASON_UNKNOWN

    return MolegDiagnosticResult(
        live_configured=live_configured,
        has_secret=has_secret,
        base_url=sanitized_base_url,
        endpoint=endpoint,
        result="source_error",
        reason_type=reason,
    )


def _response_reason(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").lower()
    try:
        if "json" in content_type:
            response.json()
        elif response.text.strip().startswith("<"):
            ElementTree.fromstring(response.text)
    except (ValueError, ElementTree.ParseError):
        return REASON_PARSE_ERROR
    return "ok"
