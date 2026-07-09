from __future__ import annotations

from time import perf_counter
from typing import Any
from urllib.parse import urlencode, urljoin
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import MolegLiveDiagnosticResult

MOLEG_LAW_SEARCH_PATH = "/DRF/lawSearch.do"
MOLEG_LAW_SERVICE_PATH = "/DRF/lawService.do"
MOLEG_LAW_TARGET = "law"
MOLEG_JSON_TYPE = "JSON"
MOLEG_XML_TYPE = "XML"
SECRET_REDACTION = "[REDACTED]"
SECRET_KEYS = {"OC", "oc", "api_key", "apikey", "MOLEG_API_KEY", "MOLEG_OC", "serviceKey", "ServiceKey"}

REASON_DNS_ERROR = "dns_error"
REASON_TIMEOUT = "timeout"
REASON_SSL_ERROR = "ssl_error"
REASON_PROXY_ERROR = "proxy_error"
REASON_CONNECTION_REFUSED = "connection_refused"
REASON_HTTP_ERROR = "http_error"
REASON_INVALID_RESPONSE = "invalid_response"
REASON_PARSE_ERROR = "parse_error"
REASON_UNKNOWN_CONNECTION_ERROR = "unknown_connection_error"
REASON_DISABLED = "disabled"
REASON_VALIDATION_ERROR = "validation_error"
REASON_OK = "ok"

MAX_RESPONSE_PREVIEW_CHARS = 700


class MolegLiveClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url if base_url is not None else settings.moleg_api_base_url).strip().rstrip("/")
        self.api_key = (api_key if api_key is not None else settings.moleg_api_key).strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.moleg_api_timeout_seconds
        self.api_enabled = settings.moleg_api_enabled if api_key is None and base_url is None else True
        self.live_test_enabled = settings.moleg_live_test_enabled

    @property
    def sanitized_base_url(self) -> str | None:
        return _sanitize_base_url(self.base_url)

    @property
    def configured(self) -> bool:
        return bool(self.api_enabled and self.base_url and self.api_key)

    @property
    def has_secret(self) -> bool:
        return bool(self.api_key)

    def search_params(self, query: str, result_type: str = MOLEG_JSON_TYPE, page: int = 1, display: int = 20) -> dict[str, str]:
        return {
            "OC": self.api_key,
            "type": result_type,
            "target": MOLEG_LAW_TARGET,
            "query": query,
            "page": str(page),
            "display": str(display),
        }

    def document_params(self, mst: str, result_type: str = MOLEG_JSON_TYPE) -> dict[str, str]:
        return {"OC": self.api_key, "type": result_type, "target": MOLEG_LAW_TARGET, "MST": mst}

    def request_payload(self, path: str, params: dict[str, str]) -> dict[str, Any] | list[Any]:
        if not self.configured:
            raise MolegLiveClientUnavailable("MOLEG API is not configured.")
        validation_error = _validate_request(path=path, params=params)
        if validation_error:
            raise MolegLiveClientError(validation_error)

        try:
            response = self._request(path=path, params=params)
        except Exception as exc:
            raise MolegLiveClientError(_classify_exception(exc)) from exc
        if response.status_code >= 400:
            raise MolegLiveClientError(REASON_HTTP_ERROR)
        return _parse_response_payload(response)

    def diagnose_law_search(self, query: str = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95") -> MolegLiveDiagnosticResult:
        endpoint = MOLEG_LAW_SEARCH_PATH
        params = self.search_params(query=query)
        validation_error = _validate_request(path=endpoint, params=params)
        base_url = self.sanitized_base_url
        final_url = _sanitized_url(base_url, endpoint, params)
        query_keys = sorted(params.keys())

        if not self.live_test_enabled:
            return self._diagnostic_result(
                endpoint=endpoint,
                params=params,
                result="skipped",
                reason_type=REASON_DISABLED,
                suggested_next_action="Set MOLEG_LIVE_TEST_ENABLED=true only in a safe local environment to run live diagnostics.",
            )
        if not self.configured:
            return self._diagnostic_result(
                endpoint=endpoint,
                params=params,
                result="source_unavailable",
                reason_type=REASON_DISABLED,
                error_message="MOLEG API base URL, enable flag, or secret is missing.",
                suggested_next_action="Check MOLEG_API_ENABLED, MOLEG_API_BASE_URL, and MOLEG_API_KEY or MOLEG_OC in local .env.",
            )
        if validation_error:
            return self._diagnostic_result(
                endpoint=endpoint,
                params=params,
                result="source_error",
                reason_type=REASON_VALIDATION_ERROR,
                error_message=validation_error,
                suggested_next_action="Verify required lawSearch.do parameters before sending the request.",
            )

        started = perf_counter()
        try:
            response = self._request(path=endpoint, params=params)
            elapsed_ms = int((perf_counter() - started) * 1000)
            reason_type = _classify_response(response)
            return MolegLiveDiagnosticResult(
                live_configured=self.configured and self.live_test_enabled,
                has_secret=self.has_secret,
                secret_exposed=False,
                sanitized_base_url=base_url,
                sanitized_endpoint=endpoint,
                final_url_sanitized=final_url,
                request_method="GET",
                query_keys=query_keys,
                timeout_seconds=self.timeout_seconds,
                status_code=response.status_code,
                reason_type=reason_type,
                error_class=None,
                error_message_sanitized=None,
                elapsed_ms=elapsed_ms,
                response_content_type=response.headers.get("content-type"),
                response_preview_sanitized=_sanitize_text(response.text, self.api_key)[:MAX_RESPONSE_PREVIEW_CHARS],
                suggested_next_action=_suggest_next_action(reason_type),
                result="ok" if reason_type == REASON_OK else "source_error",
            )
        except Exception as exc:  # diagnostic must not raise live network errors
            elapsed_ms = int((perf_counter() - started) * 1000)
            reason_type = _classify_exception(exc)
            return MolegLiveDiagnosticResult(
                live_configured=self.configured and self.live_test_enabled,
                has_secret=self.has_secret,
                secret_exposed=False,
                sanitized_base_url=base_url,
                sanitized_endpoint=endpoint,
                final_url_sanitized=final_url,
                request_method="GET",
                query_keys=query_keys,
                timeout_seconds=self.timeout_seconds,
                status_code=None,
                reason_type=reason_type,
                error_class=exc.__class__.__name__,
                error_message_sanitized=_sanitize_text(str(exc), self.api_key),
                elapsed_ms=elapsed_ms,
                response_content_type=None,
                response_preview_sanitized=None,
                suggested_next_action=_suggest_next_action(reason_type),
                result="source_error",
            )

    def _request(self, path: str, params: dict[str, str]) -> httpx.Response:
        if not self.base_url:
            raise MolegLiveClientError(REASON_DISABLED)
        return httpx.get(
            urljoin(f"{self.base_url}/", path.lstrip("/")),
            params=params,
            timeout=self.timeout_seconds,
        )

    def _diagnostic_result(
        self,
        endpoint: str,
        params: dict[str, str],
        result: str,
        reason_type: str,
        error_message: str | None = None,
        suggested_next_action: str | None = None,
    ) -> MolegLiveDiagnosticResult:
        return MolegLiveDiagnosticResult(
            live_configured=self.configured and self.live_test_enabled,
            has_secret=self.has_secret,
            secret_exposed=False,
            sanitized_base_url=self.sanitized_base_url,
            sanitized_endpoint=endpoint,
            final_url_sanitized=_sanitized_url(self.sanitized_base_url, endpoint, params),
            request_method="GET",
            query_keys=sorted(params.keys()),
            timeout_seconds=self.timeout_seconds,
            status_code=None,
            reason_type=reason_type,
            error_class=None,
            error_message_sanitized=_sanitize_text(error_message, self.api_key),
            elapsed_ms=0,
            response_content_type=None,
            response_preview_sanitized=None,
            suggested_next_action=suggested_next_action or _suggest_next_action(reason_type),
            result=result,
        )


class MolegLiveClientUnavailable(Exception):
    pass


class MolegLiveClientError(Exception):
    pass


def redact_secret_values(value: Any, secret: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: SECRET_REDACTION if key in SECRET_KEYS else redact_secret_values(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secret_values(item, secret) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value, secret)
    return value


def _validate_request(path: str, params: dict[str, str]) -> str | None:
    if not path.strip():
        return "endpoint path is required"
    if not params.get("target"):
        return "target parameter is required"
    if not params.get("type"):
        return "type parameter is required"
    if path == MOLEG_LAW_SEARCH_PATH and not params.get("query"):
        return "query parameter is required for lawSearch.do"
    if path == MOLEG_LAW_SERVICE_PATH and not params.get("MST"):
        return "MST parameter is required for lawService.do"
    if not params.get("OC"):
        return "OC parameter is required"
    return None


def _parse_response_payload(response: httpx.Response) -> dict[str, Any] | list[Any]:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        try:
            return response.json()
        except ValueError as exc:
            raise MolegLiveClientError(REASON_PARSE_ERROR) from exc
    text = response.text.strip()
    if text.startswith("{") or text.startswith("["):
        try:
            return response.json()
        except ValueError as exc:
            raise MolegLiveClientError(REASON_PARSE_ERROR) from exc
    if text.startswith("<"):
        try:
            return _xml_text_to_dict(text)
        except ElementTree.ParseError as exc:
            raise MolegLiveClientError(REASON_PARSE_ERROR) from exc
    raise MolegLiveClientError(REASON_INVALID_RESPONSE)


def _classify_response(response: httpx.Response) -> str:
    if response.status_code >= 400:
        return REASON_HTTP_ERROR
    try:
        _parse_response_payload(response)
    except MolegLiveClientError as exc:
        return str(exc) or REASON_INVALID_RESPONSE
    return REASON_OK


def _classify_exception(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, httpx.TimeoutException):
        return REASON_TIMEOUT
    if isinstance(exc, httpx.ProxyError) or "proxy" in message:
        return REASON_PROXY_ERROR
    if isinstance(exc, httpx.ConnectError):
        if any(token in message for token in ("dns", "getaddrinfo", "name or service", "nodename", "temporary failure in name resolution")):
            return REASON_DNS_ERROR
        if "ssl" in message or "certificate" in message:
            return REASON_SSL_ERROR
        if "refused" in message:
            return REASON_CONNECTION_REFUSED
        return REASON_UNKNOWN_CONNECTION_ERROR
    if isinstance(exc, httpx.HTTPStatusError) or isinstance(exc, httpx.HTTPError):
        if "ssl" in message or "certificate" in message:
            return REASON_SSL_ERROR
        return REASON_HTTP_ERROR
    if isinstance(exc, MolegLiveClientError):
        return str(exc) or REASON_INVALID_RESPONSE
    return REASON_UNKNOWN_CONNECTION_ERROR


def _sanitize_base_url(base_url: str) -> str | None:
    cleaned = (base_url or "").split("?", 1)[0].rstrip("/")
    return cleaned or None


def _sanitized_url(base_url: str | None, endpoint: str, params: dict[str, str]) -> str | None:
    if not base_url:
        return None
    safe_params = {key: SECRET_REDACTION if key in SECRET_KEYS else value for key, value in params.items()}
    return f"{urljoin(f'{base_url}/', endpoint.lstrip('/'))}?{urlencode(safe_params)}"


def _sanitize_text(value: str | None, secret: str | None = None) -> str | None:
    if value is None:
        return None
    sanitized = value
    if secret:
        sanitized = sanitized.replace(secret, SECRET_REDACTION)
    for key in SECRET_KEYS:
        sanitized = sanitized.replace(f"{key}=", f"{key}=")
    return sanitized


def _suggest_next_action(reason_type: str) -> str:
    return {
        REASON_OK: "Live endpoint responded with a parseable payload; proceed with live ingest smoke if needed.",
        REASON_DISABLED: "Enable MOLEG_API_ENABLED, MOLEG_LIVE_TEST_ENABLED, base URL, and local secret only in a safe environment.",
        REASON_VALIDATION_ERROR: "Check endpoint path and required query parameters before sending the request.",
        REASON_DNS_ERROR: "Check DNS resolution and local/network DNS policy for www.law.go.kr.",
        REASON_TIMEOUT: "Increase MOLEG_API_TIMEOUT_SECONDS or check network latency/firewall policy.",
        REASON_SSL_ERROR: "Check TLS certificate trust, SSL inspection, and corporate security middleware.",
        REASON_PROXY_ERROR: "Check HTTP_PROXY/HTTPS_PROXY/NO_PROXY environment settings.",
        REASON_CONNECTION_REFUSED: "Check outbound firewall rules and whether the remote endpoint is reachable from this machine.",
        REASON_HTTP_ERROR: "Check HTTP status, endpoint availability, and whether the OC key is authorized.",
        REASON_INVALID_RESPONSE: "Inspect sanitized response preview and confirm the expected JSON/XML response shape.",
        REASON_PARSE_ERROR: "Confirm type=JSON/XML and update parser fixtures if MOLEG changed response shape.",
    }.get(reason_type, "Review sanitized error class/message and local network policy.")


def _xml_text_to_dict(xml_text: str) -> dict[str, Any]:
    root = ElementTree.fromstring(xml_text)
    return {root.tag: _xml_element_to_value(root)}


def _xml_element_to_value(element: ElementTree.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result: dict[str, Any] = {}
    for child in children:
        child_value = _xml_element_to_value(child)
        if child.tag in result:
            existing = result[child.tag]
            if not isinstance(existing, list):
                result[child.tag] = [existing]
            result[child.tag].append(child_value)
        else:
            result[child.tag] = child_value
    return result
