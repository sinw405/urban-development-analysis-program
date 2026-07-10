from __future__ import annotations

import hashlib
import os
import socket
import ssl
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import MolegProbeResult, MolegSafeDiagnosticResponse
from app.services.moleg_live_client import (
    ALLOWED_ENV_NAMES,
    DEFAULT_LIVE_QUERY,
    FALLBACK_SOURCE_MODES,
    MOLEG_LAW_SEARCH_PATH,
    REASON_CONNECTION_REFUSED,
    REASON_CONNECTION_TIMEOUT,
    REASON_DNS_ERROR,
    REASON_INVALID_BASE_URL,
    REASON_LIVE_DISABLED,
    REASON_NOT_CONFIGURED,
    REASON_OK,
    REASON_PROXY_ERROR,
    REASON_TLS_ERROR,
    REASON_UNKNOWN_CONNECTION_ERROR,
    MolegLiveClient,
    parse_response,
    reason_message,
    retryable,
    suggested_fix,
)

PROBE_ORDER = ["config", "network", "search", "detail", "parse", "storage_policy"]


def run_moleg_live_probes(probe: str = "all", query: str = DEFAULT_LIVE_QUERY) -> MolegSafeDiagnosticResponse:
    requested = _requested_probes(probe)
    client = MolegLiveClient()
    results: dict[str, MolegProbeResult] = {}
    search_ok = False
    detail_ok = False
    parse_ok = False
    response_format = None
    sample_law_count = None
    detail_identifier = None

    if "config" in requested:
        results["config"] = _config_probe(client)
    if "network" in requested:
        results["network"] = _network_probe(client)
    if "search" in requested:
        search_diag = client.diagnose_law_search(query=query)
        results["search"] = _from_live_diag("search", search_diag)
        search_ok = search_diag.reason_type == REASON_OK
        response_format = search_diag.response_format
        sample_law_count = search_diag.sample_law_count
        if search_ok:
            try:
                search_response = client._request(MOLEG_LAW_SEARCH_PATH, client.search_params(query=query))
                parsed = parse_response(search_response)
                detail_identifier = parsed.first_law_identifier
                response_format = parsed.response_format
                sample_law_count = parsed.sample_law_count
            except Exception:
                detail_identifier = None
    if "detail" in requested:
        if not search_ok:
            results["detail"] = _probe("detail", "skipped", results.get("search", _probe("search", "skipped", REASON_NOT_CONFIGURED)).reason_type, {"skipped_reason": "search probe did not succeed"})
        elif not detail_identifier:
            results["detail"] = _probe("detail", "skipped", "invalid_response_format", {"skipped_reason": "search response did not include a law identifier"})
        else:
            detail_diag = client.diagnose_law_detail(detail_identifier)
            results["detail"] = _from_live_diag("detail", detail_diag)
            detail_ok = detail_diag.reason_type == REASON_OK
    if "parse" in requested:
        basis = results.get("detail") or results.get("search") or results.get("config")
        reason = REASON_OK if (search_ok or detail_ok) else (basis.reason_type if basis else REASON_NOT_CONFIGURED)
        status = "ok" if reason == REASON_OK else "skipped"
        parse_ok = reason == REASON_OK
        results["parse"] = _probe("parse", status, reason, {"response_format": response_format, "sample_law_count": sample_law_count})
    if "storage_policy" in requested:
        results["storage_policy"] = _probe("storage_policy", "ok", REASON_OK, {"raw_payload_stored": False, "secret_exposed": False})

    final = _final_reason(results)
    config = _config_probe(client)
    probe_list = [results[name] for name in PROBE_ORDER if name in results]
    return MolegSafeDiagnosticResponse(
        live_enabled=client.live_test_enabled,
        configured=client.configured,
        transport_ok=final == REASON_OK,
        reason_type=final,
        final_reason_type=final,
        reason_message=reason_message(final),
        reason_message_ko=reason_message(final),
        suggested_fix=suggested_fix(final),
        retryable=retryable(final),
        config_probe=results.get("config") or config,
        network_probe=results.get("network"),
        search_probe=results.get("search"),
        detail_probe=results.get("detail"),
        parse_probe=results.get("parse"),
        probe_results=probe_list,
        search_ok=search_ok,
        detail_ok=detail_ok,
        parse_ok=parse_ok,
        diagnostic_detail={
            **config.sanitized_detail,
            "allowed_env_names": ALLOWED_ENV_NAMES,
            "detected_env_names_without_values": [name for name in ALLOWED_ENV_NAMES if os.getenv(name) is not None],
        },
        next_action=suggested_fix(final),
        secret_exposed=False,
        raw_payload_stored=False,
        request_sanitized=True,
        fallback_available=True,
        fallback_source_modes=FALLBACK_SOURCE_MODES,
        checked_at=datetime.now(UTC),
        response_format=response_format,
        sample_law_count=sample_law_count,
    )


def _requested_probes(probe: str) -> set[str]:
    normalized = (probe or "all").strip().lower()
    if normalized == "all":
        return set(PROBE_ORDER)
    if normalized in PROBE_ORDER:
        return {normalized}
    return {"config"}


def _config_probe(client: MolegLiveClient) -> MolegProbeResult:
    settings = get_settings()
    if not settings.moleg_live_test_enabled:
        reason = REASON_LIVE_DISABLED
        status = "skipped"
    elif not settings.moleg_api_configured:
        reason = REASON_NOT_CONFIGURED
        status = "skipped"
    elif not _valid_base_url(settings.moleg_api_base_url):
        reason = REASON_INVALID_BASE_URL
        status = "source_error"
    else:
        reason = REASON_OK
        status = "ok"
    detail = {
        "live_enabled": settings.moleg_live_test_enabled,
        "configured": settings.moleg_api_configured,
        "key_present": bool(settings.moleg_api_key),
        "key_length": len(settings.moleg_api_key),
        "key_fingerprint_sha256_prefix": _fingerprint(settings.moleg_api_key),
        "configured_env_names": [name for name in ALLOWED_ENV_NAMES if os.getenv(name) is not None],
        "detected_env_names_without_values": [name for name in ALLOWED_ENV_NAMES if os.getenv(name) is not None],
        "base_url": _sanitize_base_url(settings.moleg_api_base_url),
        "endpoint_path": MOLEG_LAW_SEARCH_PATH,
        "timeout": settings.moleg_api_timeout_seconds,
        "retry_count": client.retry_count,
        "secret_exposed": False,
    }
    return _probe("config", status, reason, detail)


def _network_probe(client: MolegLiveClient) -> MolegProbeResult:
    settings = get_settings()
    config = _config_probe(client)
    if config.reason_type != REASON_OK:
        return _probe("network", "skipped", config.reason_type, {"skipped_reason": "config probe did not succeed"})
    parsed = urlparse(settings.moleg_api_base_url.strip())
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    started = perf_counter()
    detail: dict[str, Any] = {"host": host, "port": port, "scheme": parsed.scheme, "dns_ok": None, "socket_ok": None, "tls_ok": None}
    try:
        socket.getaddrinfo(host, port)
        detail["dns_ok"] = True
    except (socket.gaierror, OSError) as exc:
        detail.update(_error_detail(exc, started))
        return _probe("network", "source_error", REASON_DNS_ERROR, detail)
    try:
        with socket.create_connection((host, port), timeout=settings.moleg_api_timeout_seconds) as sock:
            detail["socket_ok"] = True
            if parsed.scheme == "https":
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=host):
                    detail["tls_ok"] = True
            else:
                detail["tls_ok"] = None
        detail["elapsed_ms"] = _elapsed(started)
        return _probe("network", "ok", REASON_OK, detail)
    except socket.timeout as exc:
        detail.update(_error_detail(exc, started))
        return _probe("network", "source_error", REASON_CONNECTION_TIMEOUT, detail)
    except ConnectionRefusedError as exc:
        detail.update(_error_detail(exc, started))
        return _probe("network", "source_error", REASON_CONNECTION_REFUSED, detail)
    except ssl.SSLError as exc:
        detail.update(_error_detail(exc, started))
        return _probe("network", "source_error", REASON_TLS_ERROR, detail)
    except OSError as exc:
        detail.update(_error_detail(exc, started))
        return _probe("network", "source_error", _connect_reason(exc), detail)


def _from_live_diag(name: str, diagnostic: Any) -> MolegProbeResult:
    detail = {
        "status_code": diagnostic.status_code,
        "content_type": diagnostic.response_content_type,
        "response_format": diagnostic.response_format,
        "sample_law_count": diagnostic.sample_law_count,
        "body_preview_length": len(diagnostic.response_preview_sanitized or ""),
        "final_url_sanitized": diagnostic.final_url_sanitized,
        "query_keys": diagnostic.query_keys,
        "elapsed_ms": diagnostic.elapsed_ms,
        "error_class": diagnostic.error_class,
        "error_message_sanitized": diagnostic.error_message_sanitized,
    }
    return _probe(name, "ok" if diagnostic.reason_type == REASON_OK else diagnostic.result, diagnostic.reason_type, detail)


def _probe(name: str, status: str, reason_type: str, detail: dict[str, Any] | None = None) -> MolegProbeResult:
    return MolegProbeResult(
        name=name,
        status=status,
        reason_type=reason_type,
        reason_message_ko=reason_message(reason_type),
        sanitized_detail=detail or {},
        suggested_fix=suggested_fix(reason_type),
        retryable=retryable(reason_type),
        fallback_available=True,
    )


def _final_reason(results: dict[str, MolegProbeResult]) -> str:
    for name in ("config", "network", "search", "detail", "parse"):
        result = results.get(name)
        if result and result.reason_type != REASON_OK and result.status != "skipped":
            return result.reason_type
    if results.get("search") and results["search"].reason_type == REASON_OK:
        return REASON_OK
    for name in ("config", "network", "search", "detail", "parse"):
        result = results.get(name)
        if result and result.reason_type != REASON_OK:
            return result.reason_type
    return REASON_OK


def _valid_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url or "")
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _sanitize_base_url(base_url: str) -> str | None:
    return (base_url or "").split("?", 1)[0].rstrip("/") or None


def _fingerprint(secret: str) -> str | None:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:8] if secret else None


def _elapsed(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _error_detail(exc: Exception, started: float) -> dict[str, Any]:
    return {"error_class": exc.__class__.__name__, "error_message_sanitized": str(exc)[:180], "elapsed_ms": _elapsed(started)}


def _connect_reason(exc: Exception) -> str:
    message = str(exc).lower()
    if "proxy" in message:
        return REASON_PROXY_ERROR
    if "dns" in message or "getaddrinfo" in message:
        return REASON_DNS_ERROR
    if "ssl" in message or "certificate" in message or "tls" in message:
        return REASON_TLS_ERROR
    if "refused" in message or "거부" in message:
        return REASON_CONNECTION_REFUSED
    if "timed out" in message or "timeout" in message:
        return REASON_CONNECTION_TIMEOUT
    return REASON_UNKNOWN_CONNECTION_ERROR
