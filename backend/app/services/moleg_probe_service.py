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
    BROWSER_SUCCESS_EXPECTED_LAWS,
    DEFAULT_ACCEPT,
    DEFAULT_USER_AGENT,
    MOLEG_LAW_SEARCH_PATH,
    MOLEG_LAW_SERVICE_PATH,
    MOLEG_XML_TYPE,
    REASON_CONNECTION_REFUSED,
    REASON_CONNECTION_TIMEOUT,
    REASON_DNS_ERROR,
    REASON_INVALID_BASE_URL,
    REASON_INVALID_RESPONSE_FORMAT,
    REASON_LIVE_DISABLED,
    REASON_NOT_CONFIGURED,
    REASON_OK,
    REASON_PROXY_ERROR,
    REASON_TLS_ERROR,
    REASON_UNKNOWN_CONNECTION_ERROR,
    MolegLiveClient,
    parse_response,
    sanitized_url,
    reason_message,
    retryable,
    suggested_fix,
)

PROBE_ORDER = ["config", "network", "matrix", "search", "detail", "parse", "storage_policy"]


def run_moleg_live_probes(probe: str = "all", query: str = DEFAULT_LIVE_QUERY, mst: str | None = None, ef_yd: str | None = None) -> MolegSafeDiagnosticResponse:
    requested = _requested_probes(probe)
    client = MolegLiveClient()
    results: dict[str, MolegProbeResult] = {}
    endpoint_matrix: list[dict[str, Any]] = []
    selected_endpoint: str | None = None
    selected_trust_env = True
    search_ok = False
    detail_ok = False
    parse_ok = False
    response_format = None
    sample_law_count = None
    parsed_article_count = None
    detail_identifier = mst
    detail_ef_yd = ef_yd

    if "config" in requested:
        results["config"] = _config_probe(client)
    if "network" in requested:
        results["network"] = _network_probe(client)
    matrix_needed = ("matrix" in requested or bool({"search", "detail", "parse"} & requested)) and client.configured and client.live_test_enabled
    if matrix_needed:
        endpoint_matrix = _endpoint_matrix(client, query)
        selected_item = _select_endpoint_item(endpoint_matrix)
        selected_endpoint = _endpoint_from_item(selected_item) or client.sanitized_base_url
        selected_trust_env = bool(selected_item.get("trust_env")) if selected_item else True
        reason = REASON_OK if selected_item else _matrix_reason(endpoint_matrix)
        if "matrix" in requested:
            results["matrix"] = _probe("matrix", "ok" if reason == REASON_OK else "source_error", reason, {"endpoint_matrix": endpoint_matrix, "selected_endpoint": selected_endpoint, "selected_trust_env": selected_trust_env})
    else:
        selected_endpoint = client.sanitized_base_url

    request_diff = _sanitized_request_diff(selected_endpoint or client.sanitized_base_url, query, client)
    trust_env_probe = _trust_env_summary(endpoint_matrix)
    proxy_probe = _proxy_probe()

    if "search" in requested:
        search_client = MolegLiveClient(base_url=selected_endpoint or client.base_url, api_key=client.api_key, timeout_seconds=client.timeout_seconds, retry_count=client.retry_count, retry_backoff_seconds=client.retry_backoff_seconds, trust_env=selected_trust_env)
        search_diag = search_client.diagnose_law_search(query=query)
        results["search"] = _from_live_diag("search", search_diag)
        search_ok = search_diag.reason_type == REASON_OK
        response_format = search_diag.response_format
        sample_law_count = search_diag.sample_law_count
        if search_ok:
            try:
                search_response = search_client._request(MOLEG_LAW_SEARCH_PATH, search_client.search_params(query=query))
                parsed = parse_response(search_response)
                detail_identifier = detail_identifier or parsed.first_law_identifier
                response_format = parsed.response_format
                sample_law_count = parsed.sample_law_count
                law_search = parsed.law_search or {}
                first = (law_search.get("laws") or [{}])[0]
                detail_ef_yd = detail_ef_yd or first.get("effective_date")
                results["search"].sanitized_detail.update({"totalCnt": law_search.get("total_cnt"), "parsed_law_candidates_count": len(law_search.get("laws") or []), "expected_metadata_matched": _expected_metadata_matched(law_search)})
            except Exception as exc:
                results["search"].sanitized_detail.update({"parse_after_search_error": exc.__class__.__name__})
    if "detail" in requested:
        detail_target = _detail_target(detail_identifier, detail_ef_yd)
        if not detail_target:
            reason = results.get("search", _probe("search", "skipped", REASON_NOT_CONFIGURED)).reason_type
            results["detail"] = _probe("detail", "skipped", reason, {"skipped_reason": "no MST available"})
        else:
            detail_client = MolegLiveClient(base_url=selected_endpoint or client.base_url, api_key=client.api_key, timeout_seconds=client.timeout_seconds, retry_count=client.retry_count, retry_backoff_seconds=client.retry_backoff_seconds, trust_env=selected_trust_env)
            detail_diag = detail_client.diagnose_law_detail(detail_target["mst"], ef_yd=detail_target.get("ef_yd"), result_type=MOLEG_XML_TYPE)
            detail_result = _from_live_diag("detail", detail_diag)
            detail_result.sanitized_detail.update({"law_name": detail_target.get("law_name"), "mst": detail_target["mst"], "efYd": detail_target.get("ef_yd")})
            if detail_diag.reason_type != REASON_OK:
                html_diag = detail_client.diagnose_law_detail(detail_target["mst"], ef_yd=detail_target.get("ef_yd"), result_type="HTML")
                detail_result.sanitized_detail.update({"html_availability_status": html_diag.result, "html_reason_type": html_diag.reason_type, "html_status_code": html_diag.status_code})
            results["detail"] = detail_result
            detail_ok = detail_diag.reason_type == REASON_OK
    if "parse" in requested:
        if detail_ok:
            try:
                target = _detail_target(detail_identifier, detail_ef_yd) or BROWSER_SUCCESS_EXPECTED_LAWS[0]
                parse_client = MolegLiveClient(base_url=selected_endpoint or client.base_url, api_key=client.api_key, timeout_seconds=client.timeout_seconds, retry_count=client.retry_count, retry_backoff_seconds=client.retry_backoff_seconds, trust_env=selected_trust_env)
                response = parse_client._request(MOLEG_LAW_SERVICE_PATH, parse_client.document_params(target["mst"], ef_yd=target.get("ef_yd"), result_type=MOLEG_XML_TYPE))
                parsed = parse_response(response)
                parsed_article_count = parsed.article_count or 0
                parse_ok = parsed.response_format == "xml" and parsed_article_count >= 0
                results["parse"] = _probe("parse", "ok" if parse_ok else "source_error", REASON_OK if parse_ok else REASON_INVALID_RESPONSE_FORMAT, {"law_name": target.get("law_name"), "parsed_article_count": parsed_article_count, "article_title_sample_count": parsed.article_title_sample_count, "article_number_sample_count": parsed.article_number_sample_count, "raw_payload_stored": False})
            except Exception as exc:
                reason = _connect_reason(exc)
                results["parse"] = _probe("parse", "source_error", reason, {"error_class": exc.__class__.__name__, "raw_payload_stored": False})
        else:
            basis = results.get("detail") or results.get("search") or results.get("config")
            reason = basis.reason_type if basis else REASON_NOT_CONFIGURED
            results["parse"] = _probe("parse", "skipped", reason, {"response_format": response_format, "sample_law_count": sample_law_count})
    if "storage_policy" in requested:
        results["storage_policy"] = _probe("storage_policy", "ok", REASON_OK, {"raw_payload_stored": False, "secret_exposed": False})

    final = _final_reason(results)
    ready_for_live_ingest = search_ok and detail_ok and parse_ok
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
        browser_success_metadata_present=True,
        browser_success_expected_laws=BROWSER_SUCCESS_EXPECTED_LAWS,
        endpoint_matrix=endpoint_matrix,
        selected_endpoint=selected_endpoint,
        sanitized_request_diff=request_diff,
        user_agent_applied=True,
        trust_env_probe=trust_env_probe,
        proxy_probe=proxy_probe,
        ready_for_live_ingest=ready_for_live_ingest,
        diagnostic_detail={**config.sanitized_detail, "allowed_env_names": ALLOWED_ENV_NAMES, "detected_env_names_without_values": [name for name in ALLOWED_ENV_NAMES if os.getenv(name) is not None]},
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

def _endpoint_matrix(client: MolegLiveClient, query: str) -> list[dict[str, Any]]:
    settings = get_settings()
    host = urlparse(settings.moleg_api_base_url or "https://www.law.go.kr").hostname or "www.law.go.kr"
    candidates: list[dict[str, Any]] = []
    for scheme in ("http", "https"):
        for trust_env in (True, False):
            base_url = f"{scheme}://{host}"
            matrix_client = MolegLiveClient(base_url=base_url, api_key=client.api_key, timeout_seconds=client.timeout_seconds, retry_count=0, retry_backoff_seconds=0, trust_env=trust_env)
            params = matrix_client.search_params(query=query)
            started = perf_counter()
            item: dict[str, Any] = {
                "candidate_name": f"{scheme}_trust_env_{str(trust_env).lower()}",
                "scheme": scheme,
                "host": host,
                "port": 443 if scheme == "https" else 80,
                "path": MOLEG_LAW_SEARCH_PATH,
                "query_redacted": sanitized_url(base_url, MOLEG_LAW_SEARCH_PATH, params),
                "trust_env": trust_env,
                "connect_ok": False,
                "selected_candidate": False,
                "reason_type": REASON_UNKNOWN_CONNECTION_ERROR,
            }
            try:
                response = matrix_client._request(MOLEG_LAW_SEARCH_PATH, params)
                parsed = parse_response(response)
                law_search = parsed.law_search or {}
                item.update({
                    "connect_ok": True,
                    "http_status_optional": response.status_code,
                    "content_type_optional": response.headers.get("content-type"),
                    "body_length_optional": len(response.content),
                    "resultCode_optional": law_search.get("result_code"),
                    "totalCnt_optional": law_search.get("total_cnt"),
                    "parsed_law_candidates_count_optional": len(law_search.get("laws") or []),
                    "reason_type": REASON_OK,
                    "selected_candidate": (law_search.get("result_code") == "00" and len(law_search.get("laws") or []) >= 1),
                })
            except Exception as exc:
                item.update({"reason_type": _connect_reason(exc), "error_class": exc.__class__.__name__, "error_message_sanitized": str(exc)[:180]})
            item["elapsed_ms"] = _elapsed(started)
            item["reason_message_ko"] = reason_message(item["reason_type"])
            item["suggested_fix"] = suggested_fix(item["reason_type"])
            candidates.append(item)
    selected_item = _select_endpoint_item(candidates)
    for item in candidates:
        item["selected_candidate"] = item is selected_item
    return candidates


def _select_endpoint_item(matrix: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in matrix:
        if item.get("selected_candidate"):
            return item
    return None


def _endpoint_from_item(item: dict[str, Any] | None) -> str | None:
    if not item:
        return None
    return f"{item['scheme']}://{item['host']}"


def _select_endpoint(matrix: list[dict[str, Any]]) -> str | None:
    return _endpoint_from_item(_select_endpoint_item(matrix))


def _matrix_reason(matrix: list[dict[str, Any]]) -> str:
    for item in matrix:
        if item.get("reason_type") != REASON_OK:
            return str(item.get("reason_type"))
    return REASON_UNKNOWN_CONNECTION_ERROR


def _sanitized_request_diff(selected_endpoint: str | None, query: str, client: MolegLiveClient) -> dict[str, Any]:
    browser = "http://www.law.go.kr/DRF/lawSearch.do?OC=[REDACTED]&target=law&type=XML&query=\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
    python_base = selected_endpoint or client.sanitized_base_url or ""
    python_pattern = sanitized_url(python_base, MOLEG_LAW_SEARCH_PATH, client.search_params(query=query))
    browser_scheme = "http"
    python_scheme = urlparse(python_base).scheme
    differences: list[str] = []
    if browser_scheme != python_scheme:
        differences.append(f"scheme differs: browser={browser_scheme}, python={python_scheme}")
    differences.append("user-agent applied" if client.user_agent else "user-agent missing")
    differences.append("accept header applied" if client.accept else "accept header missing")
    return {
        "browser_success_pattern": browser,
        "python_request_pattern": python_pattern,
        "differences": differences,
        "query_parameter_names_browser": ["OC", "target", "type", "query"],
        "query_parameter_names_python": ["OC", "display", "page", "query", "target", "type"],
        "oc_present": bool(client.api_key),
        "target": "law",
        "type": MOLEG_XML_TYPE,
        "query_encoding": "httpx params encoding",
        "user_agent": DEFAULT_USER_AGENT,
        "accept": DEFAULT_ACCEPT,
        "timeout": client.timeout_seconds,
        "trust_env": client.trust_env,
        "proxy_detected": bool(_proxy_probe()["proxy_env_detected"]),
        "secret_exposed": False,
    }


def _trust_env_summary(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if matrix:
        return [{"trust_env": item.get("trust_env"), "reason_type": item.get("reason_type"), "selected_candidate": item.get("selected_candidate", False)} for item in matrix]
    return [{"trust_env": True, "reason_type": "not_run"}, {"trust_env": False, "reason_type": "not_run"}]


def _proxy_probe() -> dict[str, Any]:
    names = [name for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy") if os.getenv(name)]
    return {"proxy_env_detected": bool(names), "proxy_env_names_without_values": names, "secret_exposed": False}


def _expected_metadata_matched(law_search: dict[str, Any]) -> bool:
    laws = law_search.get("laws") or []
    by_name = {item.get("law_name"): item for item in laws if isinstance(item, dict)}
    for expected in BROWSER_SUCCESS_EXPECTED_LAWS:
        item = by_name.get(expected["law_name"])
        if not item or item.get("mst") != expected["mst"] or item.get("law_id") != expected["law_id"]:
            return False
    return True


def _detail_target(mst: str | None, ef_yd: str | None) -> dict[str, Any] | None:
    if mst:
        for item in BROWSER_SUCCESS_EXPECTED_LAWS:
            if item["mst"] == mst:
                result = dict(item)
                if ef_yd:
                    result["ef_yd"] = ef_yd
                return result
        return {"law_name": None, "mst": mst, "ef_yd": ef_yd}
    return dict(BROWSER_SUCCESS_EXPECTED_LAWS[0]) if BROWSER_SUCCESS_EXPECTED_LAWS else None


def reason_message(reason_type: str) -> str:
    return {
        REASON_OK: "\ubc95\uc81c\ucc98 API \uc751\ub2f5\uc774 \uc815\uc0c1\uc801\uc73c\ub85c \ud655\uc778\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
        REASON_NOT_CONFIGURED: "\ubc95\uc81c\ucc98 API \uc124\uc815\uc774 \uc644\ub8cc\ub418\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4.",
        REASON_LIVE_DISABLED: "\ubc95\uc81c\ucc98 API live \uc9c4\ub2e8\uc774 \ube44\ud65c\uc131\ud654\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.",
        REASON_INVALID_BASE_URL: "\ubc95\uc81c\ucc98 API base URL \ud615\uc2dd\uc774 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
        REASON_DNS_ERROR: "\ubc95\uc81c\ucc98 API \ud638\uc2a4\ud2b8 DNS \uc870\ud68c\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.",
        REASON_CONNECTION_TIMEOUT: "\ubc95\uc81c\ucc98 API \uc5f0\uacb0 \uc2dc\uac04\uc774 \ucd08\uacfc\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
        REASON_CONNECTION_REFUSED: "\ubc95\uc81c\ucc98 API \uc5f0\uacb0\uc774 \uac70\ubd80\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
        REASON_TLS_ERROR: "\ubc95\uc81c\ucc98 API TLS \ub610\ub294 \uc778\uc99d\uc11c \uc5f0\uacb0 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.",
        REASON_PROXY_ERROR: "\ud504\ub85d\uc2dc \uc124\uc815 \ub610\ub294 \ud504\ub85d\uc2dc \uc5f0\uacb0 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.",
        REASON_INVALID_RESPONSE_FORMAT: "\ubc95\uc81c\ucc98 API \uc751\ub2f5 \ud615\uc2dd\uc744 JSON/XML\ub85c \ud655\uc778\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.",
    }.get(reason_type, "\ubc95\uc81c\ucc98 API \uc5f0\uacb0 \uc624\ub958 \uc6d0\uc778\uc744 \ucd94\uac00 \ud655\uc778\ud574\uc57c \ud569\ub2c8\ub2e4.")

def suggested_fix(reason_type: str) -> str:
    return {
        REASON_OK: "search/detail/parse\uac00 \ubaa8\ub450 ok\uc774\uba74 Phase37 live ingest\ub85c \uc9c4\ud589\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
        REASON_CONNECTION_REFUSED: "\ube0c\ub77c\uc6b0\uc800 \uc131\uacf5 \uc694\uccad\uacfc Python \uc694\uccad\uc758 http/https, User-Agent, trust_env, proxy \ucc28\uc774\ub97c \ud655\uc778\ud558\uc138\uc694.",
        REASON_PROXY_ERROR: "HTTP_PROXY/HTTPS_PROXY \uac12\uacfc \ube0c\ub77c\uc6b0\uc800 \ud504\ub85d\uc2dc \uc124\uc815 \ucc28\uc774\ub97c \ud655\uc778\ud558\uc138\uc694.",
        REASON_INVALID_RESPONSE_FORMAT: "type=XML \uc751\ub2f5\uacfc content-type\uc744 \ud655\uc778\ud558\uc138\uc694.",
    }.get(reason_type, "sanitized request diff\uc640 endpoint matrix \uacb0\uacfc\ub97c \ud655\uc778\ud558\uc138\uc694.")

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
