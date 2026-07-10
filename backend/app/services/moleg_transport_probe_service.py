from __future__ import annotations

import os
import socket
import ssl
from time import perf_counter
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import MolegTransportDiagnosticResponse
from app.services.moleg_live_client import (
    ALLOWED_ENV_NAMES,
    FALLBACK_SOURCE_MODES,
    MOLEG_LAW_SEARCH_PATH,
    REASON_CONNECTION_REFUSED,
    REASON_CONNECTION_TIMEOUT,
    REASON_DNS_ERROR,
    REASON_HTTP_ERROR_STATUS,
    REASON_INVALID_BASE_URL,
    REASON_LIVE_DISABLED,
    REASON_NOT_CONFIGURED,
    REASON_OK,
    REASON_TLS_ERROR,
    REASON_UNKNOWN_CONNECTION_ERROR,
    SECRET_REDACTION,
    reason_message,
)

MAX_PREVIEW_CHARS = 500


def diagnose_moleg_transport() -> MolegTransportDiagnosticResponse:
    settings = get_settings()
    base_url = settings.moleg_api_base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    scheme = parsed.scheme or None
    host = parsed.hostname
    port = parsed.port or (443 if scheme == "https" else 80 if scheme == "http" else None)
    endpoint = MOLEG_LAW_SEARCH_PATH
    started = perf_counter()
    proxy_detected = any(os.getenv(name) for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"))
    has_secret = bool(settings.moleg_api_key)
    live_enabled = settings.moleg_live_test_enabled
    configured = settings.moleg_api_configured and bool(host) and scheme in {"http", "https"}
    live_configured = settings.moleg_live_test_configured and bool(host) and scheme in {"http", "https"}
    final_url = _final_url(base_url, endpoint)

    result = MolegTransportDiagnosticResponse(
        live_configured=live_configured,
        configured=configured,
        live_enabled=live_enabled,
        has_secret=has_secret,
        key_present=has_secret,
        key_length=len(settings.moleg_api_key),
        key_fingerprint=_fingerprint(settings.moleg_api_key),
        configured_env_names=[name for name in ALLOWED_ENV_NAMES if os.getenv(name) is not None],
        allowed_env_names=ALLOWED_ENV_NAMES,
        base_url_configured=bool(base_url),
        timeout_seconds=settings.moleg_api_timeout_seconds,
        retry_count=int(os.getenv("MOLEG_API_RETRY_COUNT", "1") or "1"),
        backoff_seconds=_env_float("MOLEG_API_RETRY_BACKOFF_SECONDS", 0.25),
        secret_exposed=False,
        sanitized_base_url=_sanitize_base_url(base_url),
        sanitized_endpoint=endpoint,
        host=host,
        port=port,
        scheme=scheme,
        proxy_detected=proxy_detected,
        dns_ok=None,
        socket_ok=None,
        tls_ok=None,
        http_ok=None,
        endpoint_ok=None,
        status_code=None,
        reason_type=REASON_UNKNOWN_CONNECTION_ERROR,
        error_class=None,
        error_message_sanitized=None,
        elapsed_ms=0,
        suggested_next_action="Check MOLEG configuration before running transport diagnostics.",
        reason_message=reason_message(REASON_UNKNOWN_CONNECTION_ERROR),
        final_url_sanitized=final_url,
        response_preview_sanitized=None,
        request_sanitized=True,
        raw_payload_stored=False,
        fallback_available=True,
        fallback_source_modes=FALLBACK_SOURCE_MODES,
    )

    if not live_enabled:
        return _finish(result, started, REASON_LIVE_DISABLED, "Set MOLEG_LIVE_TEST_ENABLED=true only in a safe local environment to run transport diagnostics.")
    if not settings.moleg_api_configured:
        return _finish(result, started, REASON_NOT_CONFIGURED, "Check MOLEG_API_ENABLED, MOLEG_API_BASE_URL, and MOLEG_API_KEY or MOLEG_OC in local .env.")
    if not host or port is None or scheme not in {"http", "https"}:
        result.error_message_sanitized = "MOLEG_API_BASE_URL must include http or https scheme and host."
        return _finish(result, started, REASON_INVALID_BASE_URL, "Set MOLEG_API_BASE_URL to a full base URL such as https://www.law.go.kr.")

    try:
        socket.getaddrinfo(host, port)
        result.dns_ok = True
    except (socket.gaierror, OSError) as exc:
        return _fail(result, started, REASON_DNS_ERROR, exc, "Check DNS resolution for the configured MOLEG host.")

    try:
        with socket.create_connection((host, port), timeout=settings.moleg_api_timeout_seconds) as sock:
            result.socket_ok = True
            if scheme == "https":
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=host):
                    result.tls_ok = True
            else:
                result.tls_ok = None
    except socket.timeout as exc:
        return _fail(result, started, REASON_CONNECTION_TIMEOUT, exc, "Check network latency, firewall policy, or increase MOLEG_API_TIMEOUT_SECONDS.")
    except ConnectionRefusedError as exc:
        return _fail(result, started, REASON_CONNECTION_REFUSED, exc, "Check outbound firewall rules and remote endpoint reachability.")
    except ssl.SSLError as exc:
        return _fail(result, started, REASON_TLS_ERROR, exc, "Check TLS certificate trust, SSL inspection, and local certificate store.")
    except OSError as exc:
        return _fail(result, started, _connect_reason(exc), exc, "Check socket connectivity, proxy, and firewall settings.")

    try:
        response = httpx.get(
            urljoin(f"{base_url}/", endpoint.lstrip("/")),
            params={"target": "law", "type": "JSON", "query": "healthcheck", "OC": SECRET_REDACTION},
            timeout=settings.moleg_api_timeout_seconds,
        )
        result.status_code = response.status_code
        result.http_ok = response.status_code < 500
        result.endpoint_ok = response.status_code < 400
        result.response_preview_sanitized = _preview(response.text)
        if response.status_code >= 400:
            return _finish(result, started, REASON_HTTP_ERROR_STATUS, "HTTP transport reached the endpoint; check status code and OC authorization with a real local secret.")
        return _finish(result, started, REASON_OK, "Transport probe reached the endpoint; continue with live diagnostic or live ingest smoke.")
    except httpx.TimeoutException as exc:
        return _fail(result, started, REASON_CONNECTION_TIMEOUT, exc, "HTTP request timed out; check network or timeout settings.")
    except httpx.ConnectError as exc:
        return _fail(result, started, _connect_reason(exc), exc, "Check sanitized error class/message and network path.")
    except httpx.HTTPError as exc:
        return _fail(result, started, REASON_HTTP_ERROR_STATUS, exc, "HTTP client failed after socket/TLS checks; inspect local proxy or TLS middleware.")


def _finish(result: MolegTransportDiagnosticResponse, started: float, reason_type: str, action: str) -> MolegTransportDiagnosticResponse:
    result.reason_type = reason_type
    result.reason_message = reason_message(reason_type)
    result.elapsed_ms = _elapsed(started)
    result.suggested_next_action = action
    return result


def _fail(result: MolegTransportDiagnosticResponse, started: float, reason_type: str, exc: Exception, action: str) -> MolegTransportDiagnosticResponse:
    result.error_class = exc.__class__.__name__
    result.error_message_sanitized = _sanitize_text(str(exc))
    return _finish(result, started, reason_type, action)


def _connect_reason(exc: Exception) -> str:
    message = str(exc).lower()
    if "dns" in message or "getaddrinfo" in message:
        return REASON_DNS_ERROR
    if "ssl" in message or "certificate" in message or "tls" in message:
        return REASON_TLS_ERROR
    if "refused" in message:
        return REASON_CONNECTION_REFUSED
    if "timed out" in message or "timeout" in message:
        return REASON_CONNECTION_TIMEOUT
    return REASON_UNKNOWN_CONNECTION_ERROR


def _elapsed(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _sanitize_base_url(base_url: str) -> str | None:
    cleaned = base_url.split("?", 1)[0].rstrip("/")
    return cleaned or None


def _final_url(base_url: str, endpoint: str) -> str | None:
    if not base_url:
        return None
    sanitized = _sanitize_base_url(base_url)
    if not sanitized:
        return None
    return f"{urljoin(f'{sanitized}/', endpoint.lstrip('/'))}?target=law&type=JSON&query=healthcheck&OC={SECRET_REDACTION}"


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = value
    for name in ("MOLEG_API_KEY", "MOLEG_OC"):
        secret = os.getenv(name)
        if secret:
            sanitized = sanitized.replace(secret, SECRET_REDACTION)
    return sanitized


def _preview(value: str) -> str:
    return _sanitize_text(value[:MAX_PREVIEW_CHARS]) or ""


def _fingerprint(secret: str) -> str | None:
    if not secret:
        return None
    import hashlib

    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:8]


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except ValueError:
        return default
