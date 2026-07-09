from __future__ import annotations

import os
import socket
import ssl
from time import perf_counter
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import MolegTransportDiagnosticResponse
from app.services.moleg_live_client import MOLEG_LAW_SEARCH_PATH, SECRET_REDACTION

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
    live_configured = settings.moleg_live_test_configured
    final_url = _final_url(base_url, endpoint)

    result = MolegTransportDiagnosticResponse(
        live_configured=live_configured,
        has_secret=has_secret,
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
        reason_type="disabled" if not live_configured else "unknown_connection_error",
        error_class=None,
        error_message_sanitized=None,
        elapsed_ms=0,
        suggested_next_action="Check MOLEG configuration before running transport diagnostics.",
        final_url_sanitized=final_url,
        response_preview_sanitized=None,
    )

    if not live_configured:
        result.elapsed_ms = _elapsed(started)
        result.reason_type = "disabled"
        result.suggested_next_action = "Check MOLEG_API_ENABLED, MOLEG_LIVE_TEST_ENABLED, MOLEG_API_BASE_URL, and local secret configuration."
        return result
    if not host or port is None or scheme not in {"http", "https"}:
        result.elapsed_ms = _elapsed(started)
        result.reason_type = "invalid_response"
        result.error_message_sanitized = "MOLEG_API_BASE_URL must include http or https scheme and host."
        result.suggested_next_action = "Set MOLEG_API_BASE_URL to a full base URL such as https://www.law.go.kr."
        return result

    try:
        socket.getaddrinfo(host, port)
        result.dns_ok = True
    except (socket.gaierror, OSError) as exc:
        return _fail(result, started, "dns_error", exc, "Check DNS resolution for the configured MOLEG host.")

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
        return _fail(result, started, "socket_timeout", exc, "Check network latency, firewall policy, or increase MOLEG_API_TIMEOUT_SECONDS.")
    except ConnectionRefusedError as exc:
        return _fail(result, started, "connection_refused", exc, "Check outbound firewall rules and remote endpoint reachability.")
    except ssl.SSLError as exc:
        return _fail(result, started, "tls_error", exc, "Check TLS certificate trust, SSL inspection, and local certificate store.")
    except OSError as exc:
        reason = "socket_connection_error"
        if "proxy" in str(exc).lower():
            reason = "proxy_error"
        return _fail(result, started, reason, exc, "Check socket connectivity, proxy, and firewall settings.")

    try:
        response = httpx.get(urljoin(f"{base_url}/", endpoint.lstrip("/")), params={"target": "law", "type": "JSON", "query": "healthcheck", "OC": SECRET_REDACTION}, timeout=settings.moleg_api_timeout_seconds)
        result.status_code = response.status_code
        result.http_ok = response.status_code < 500
        result.endpoint_ok = response.status_code < 400
        result.response_preview_sanitized = _preview(response.text)
        if response.status_code >= 400:
            result.reason_type = "http_error"
            result.suggested_next_action = "HTTP transport reached the endpoint; check status code and OC authorization with a real local secret."
        else:
            result.reason_type = "ok"
            result.suggested_next_action = "Transport probe reached the endpoint; continue with live diagnostic or live ingest smoke."
    except httpx.TimeoutException as exc:
        return _fail(result, started, "socket_timeout", exc, "HTTP request timed out; check network or timeout settings.")
    except httpx.ProxyError as exc:
        return _fail(result, started, "proxy_error", exc, "Check HTTP_PROXY/HTTPS_PROXY/NO_PROXY settings.")
    except httpx.ConnectError as exc:
        return _fail(result, started, _connect_reason(exc), exc, "Check sanitized error class/message and network path.")
    except httpx.HTTPError as exc:
        return _fail(result, started, "http_error", exc, "HTTP client failed after socket/TLS checks; inspect local proxy or TLS middleware.")

    result.elapsed_ms = _elapsed(started)
    return result


def _fail(result: MolegTransportDiagnosticResponse, started: float, reason_type: str, exc: Exception, action: str) -> MolegTransportDiagnosticResponse:
    result.reason_type = reason_type
    result.error_class = exc.__class__.__name__
    result.error_message_sanitized = _sanitize_text(str(exc))
    result.elapsed_ms = _elapsed(started)
    result.suggested_next_action = action
    return result


def _connect_reason(exc: Exception) -> str:
    message = str(exc).lower()
    if "dns" in message or "getaddrinfo" in message:
        return "dns_error"
    if "ssl" in message or "certificate" in message:
        return "ssl_error"
    if "refused" in message:
        return "connection_refused"
    if "proxy" in message:
        return "proxy_error"
    return "unknown_connection_error"


def _elapsed(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _sanitize_base_url(base_url: str) -> str | None:
    cleaned = base_url.split("?", 1)[0].rstrip("/")
    return cleaned or None


def _final_url(base_url: str, endpoint: str) -> str | None:
    if not base_url:
        return None
    return f"{urljoin(f'{_sanitize_base_url(base_url)}/', endpoint.lstrip('/'))}?target=law&type=JSON&query=healthcheck&OC={SECRET_REDACTION}"


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace(os.getenv("MOLEG_API_KEY", "__NO_KEY__"), SECRET_REDACTION).replace(os.getenv("MOLEG_OC", "__NO_OC__"), SECRET_REDACTION)


def _preview(value: str) -> str:
    return _sanitize_text(value[:MAX_PREVIEW_CHARS]) or ""
