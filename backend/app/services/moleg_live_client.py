from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from time import perf_counter, sleep
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import MolegLiveDiagnosticResult

MOLEG_LAW_SEARCH_PATH = "/DRF/lawSearch.do"
MOLEG_LAW_SERVICE_PATH = "/DRF/lawService.do"
MOLEG_LAW_TARGET = "law"
MOLEG_JSON_TYPE = "JSON"
MOLEG_XML_TYPE = "XML"
DEFAULT_LIVE_QUERY = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
MOLEG_HTML_TYPE = "HTML"
DEFAULT_USER_AGENT = "Mozilla/5.0 compatible; UrbanDevelopmentAnalysis/0.1; MOLEG-live-probe"
DEFAULT_ACCEPT = "application/xml,text/xml,application/json,*/*"
BROWSER_SUCCESS_EXPECTED_LAWS = [
    {"law_name": "\ub3c4\uc2dc\uac1c\ubc1c\ubc95", "mst": "284059", "law_id": "002024", "ef_yd": "20260701"},
    {"law_name": "\ub3c4\uc2dc\uac1c\ubc1c\ubc95 \uc2dc\ud589\ub839", "mst": "287279", "law_id": "003421", "ef_yd": "20260701"},
    {"law_name": "\ub3c4\uc2dc\uac1c\ubc1c\ubc95 \uc2dc\ud589\uaddc\uce59", "mst": "268933", "law_id": "007096", "ef_yd": "20250131"},
]
SECRET_REDACTION = "[REDACTED]"
SECRET_KEYS = {"OC", "oc", "api_key", "apikey", "MOLEG_API_KEY", "MOLEG_OC", "serviceKey", "ServiceKey", "key", "token", "access_token"}
ALLOWED_ENV_NAMES = ["MOLEG_API_ENABLED", "MOLEG_LIVE_TEST_ENABLED", "MOLEG_API_BASE_URL", "MOLEG_API_KEY", "MOLEG_OC", "MOLEG_API_TIMEOUT_SECONDS", "MOLEG_API_RETRY_COUNT", "MOLEG_API_RETRY_BACKOFF_SECONDS"]
FALLBACK_SOURCE_MODES = ["official_seed_db", "official_manual_db", "procedure_keyword_candidate", "needs_review"]

REASON_OK = "ok"
REASON_NOT_CONFIGURED = "not_configured"
REASON_LIVE_DISABLED = "live_disabled"
REASON_INVALID_BASE_URL = "invalid_base_url"
REASON_DNS_ERROR = "dns_error"
REASON_CONNECTION_TIMEOUT = "connection_timeout"
REASON_CONNECTION_REFUSED = "connection_refused"
REASON_TLS_ERROR = "tls_error"
REASON_PROXY_ERROR = "proxy_error"
REASON_HTTP_ERROR_STATUS = "http_error_status"
REASON_UNAUTHORIZED_OR_INVALID_KEY = "unauthorized_or_invalid_key"
REASON_INVALID_REQUEST_PARAMETER = "invalid_request_parameter"
REASON_INVALID_RESPONSE_FORMAT = "invalid_response_format"
REASON_EMPTY_RESPONSE = "empty_response"
REASON_HTML_ERROR_RESPONSE = "html_error_response"
REASON_API_ERROR_RESPONSE = "api_error_response"
REASON_PARSING_ERROR = "parsing_error"
REASON_UNKNOWN_CONNECTION_ERROR = "unknown_connection_error"

# Backward-compatible aliases used by older modules/tests.
REASON_TIMEOUT = REASON_CONNECTION_TIMEOUT
REASON_SSL_ERROR = REASON_TLS_ERROR
REASON_HTTP_ERROR = REASON_HTTP_ERROR_STATUS
REASON_INVALID_RESPONSE = REASON_INVALID_RESPONSE_FORMAT
REASON_PARSE_ERROR = REASON_PARSING_ERROR
REASON_DISABLED = REASON_LIVE_DISABLED
REASON_VALIDATION_ERROR = REASON_INVALID_RESPONSE_FORMAT

MAX_RESPONSE_PREVIEW_CHARS = 500


@dataclass(frozen=True)
class ParsedMolegResponse:
    payload: dict[str, Any] | list[Any]
    response_format: str | None
    sample_law_count: int | None
    first_law_identifier: str | None = None
    article_count: int | None = None
    law_search: dict[str, Any] | None = None
    article_title_sample_count: int = 0
    article_number_sample_count: int = 0


class MolegLiveClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        retry_count: int | None = None,
        retry_backoff_seconds: float | None = None,
        trust_env: bool | None = None,
        user_agent: str | None = None,
        accept: str | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url if base_url is not None else settings.moleg_api_base_url).strip().rstrip("/")
        self.api_key = (api_key if api_key is not None else settings.moleg_api_key).strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.moleg_api_timeout_seconds
        self.retry_count = retry_count if retry_count is not None else int(os.getenv("MOLEG_API_RETRY_COUNT", "1") or "1")
        self.retry_backoff_seconds = retry_backoff_seconds if retry_backoff_seconds is not None else _env_float("MOLEG_API_RETRY_BACKOFF_SECONDS", 0.25)
        self.api_enabled = settings.moleg_api_enabled if api_key is None and base_url is None else True
        self.live_test_enabled = settings.moleg_live_test_enabled
        self.trust_env = True if trust_env is None else trust_env
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.accept = accept or DEFAULT_ACCEPT

    @property
    def sanitized_base_url(self) -> str | None:
        return _sanitize_base_url(self.base_url)

    @property
    def configured(self) -> bool:
        return bool(self.api_enabled and self.base_url and self.api_key and _valid_base_url(self.base_url))

    @property
    def has_secret(self) -> bool:
        return bool(self.api_key)

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": self.accept}

    def search_params(self, query: str, result_type: str = MOLEG_XML_TYPE, page: int = 1, display: int = 5) -> dict[str, str]:
        return {
            "OC": self.api_key,
            "type": result_type,
            "target": MOLEG_LAW_TARGET,
            "query": query,
            "page": str(page),
            "display": str(display),
        }

    def document_params(self, mst: str, result_type: str = MOLEG_XML_TYPE, ef_yd: str | None = None) -> dict[str, str]:
        params = {"OC": self.api_key, "type": result_type, "target": MOLEG_LAW_TARGET, "MST": mst}
        if ef_yd:
            params["efYd"] = ef_yd
        return params

    def request_payload(self, path: str, params: dict[str, str]) -> dict[str, Any] | list[Any]:
        if not self.api_enabled:
            raise MolegLiveClientUnavailable(REASON_LIVE_DISABLED)
        if not self.base_url or not self.api_key:
            raise MolegLiveClientUnavailable(REASON_NOT_CONFIGURED)
        validation_error = _validate_request(path=path, params=params, base_url=self.base_url)
        if validation_error:
            raise MolegLiveClientError(validation_error)
        try:
            response = self._request(path=path, params=params)
        except Exception as exc:
            raise MolegLiveClientError(_classify_exception(exc)) from exc
        reason = _classify_http_response(response)
        if reason != REASON_OK:
            raise MolegLiveClientError(reason)
        parsed = parse_response(response)
        if _payload_has_api_error(parsed.payload):
            raise MolegLiveClientError(_api_error_reason(parsed.payload))
        return parsed.payload

    def diagnose_law_search(self, query: str = DEFAULT_LIVE_QUERY) -> MolegLiveDiagnosticResult:
        return self.diagnose_request(endpoint=MOLEG_LAW_SEARCH_PATH, params=self.search_params(query=query), require_live=True)

    def diagnose_law_detail(self, mst: str, ef_yd: str | None = None, result_type: str = MOLEG_XML_TYPE) -> MolegLiveDiagnosticResult:
        return self.diagnose_request(endpoint=MOLEG_LAW_SERVICE_PATH, params=self.document_params(mst=mst, ef_yd=ef_yd, result_type=result_type), require_live=True)

    def diagnose_request(self, endpoint: str, params: dict[str, str], require_live: bool = True) -> MolegLiveDiagnosticResult:
        validation_error = _validate_request(path=endpoint, params=params, base_url=self.base_url)
        base_url = self.sanitized_base_url
        final_url = _sanitized_url(base_url, endpoint, params)
        query_keys = sorted(params.keys())

        if require_live and not self.live_test_enabled:
            return self._diagnostic_result(endpoint=endpoint, params=params, result="skipped", reason_type=REASON_LIVE_DISABLED)
        if not self.api_enabled or not self.base_url or not self.api_key:
            return self._diagnostic_result(endpoint=endpoint, params=params, result="skipped", reason_type=REASON_NOT_CONFIGURED, error_message="MOLEG API base URL, enable flag, or secret is missing.")
        if validation_error:
            return self._diagnostic_result(endpoint=endpoint, params=params, result="source_error", reason_type=validation_error, error_message=validation_error)

        started = perf_counter()
        try:
            response = self._request(path=endpoint, params=params)
            elapsed_ms = int((perf_counter() - started) * 1000)
            reason_type = _classify_http_response(response)
            response_format = None
            sample_law_count = None
            if reason_type == REASON_OK:
                try:
                    parsed = parse_response(response)
                    response_format = parsed.response_format
                    sample_law_count = parsed.sample_law_count
                    if _payload_has_api_error(parsed.payload):
                        reason_type = _api_error_reason(parsed.payload)
                except MolegLiveClientError as exc:
                    reason_type = str(exc) or REASON_INVALID_RESPONSE_FORMAT
            return self._result_model(
                endpoint=endpoint,
                params=params,
                base_url=base_url,
                final_url=final_url,
                query_keys=query_keys,
                status_code=response.status_code,
                reason_type=reason_type,
                error_class=None,
                error_message_sanitized=None,
                elapsed_ms=elapsed_ms,
                response_content_type=response.headers.get("content-type"),
                response_preview_sanitized=_safe_response_preview(response.text, self.api_key),
                suggested_next_action=suggested_fix(reason_type),
                result="ok" if reason_type == REASON_OK else "source_error",
                response_format=response_format,
                sample_law_count=sample_law_count,
            )
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started) * 1000)
            reason_type = _classify_exception(exc)
            return self._result_model(
                endpoint=endpoint,
                params=params,
                base_url=base_url,
                final_url=final_url,
                query_keys=query_keys,
                status_code=None,
                reason_type=reason_type,
                error_class=exc.__class__.__name__,
                error_message_sanitized=_sanitize_text(str(exc), self.api_key),
                elapsed_ms=elapsed_ms,
                response_content_type=None,
                response_preview_sanitized=None,
                suggested_next_action=suggested_fix(reason_type),
                result="source_error",
                response_format=None,
                sample_law_count=None,
            )

    def _request(self, path: str, params: dict[str, str]) -> httpx.Response:
        if not self.base_url:
            raise MolegLiveClientError(REASON_NOT_CONFIGURED)
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        attempts = max(0, self.retry_count) + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return _http_get(
                    url,
                    params=params,
                    timeout=httpx.Timeout(self.timeout_seconds),
                    headers=self.headers,
                    trust_env=self.trust_env,
                )
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ProxyError) as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                sleep(max(0.0, self.retry_backoff_seconds) * (2 ** attempt))
        assert last_exc is not None
        raise last_exc

    def _diagnostic_result(self, endpoint: str, params: dict[str, str], result: str, reason_type: str, error_message: str | None = None) -> MolegLiveDiagnosticResult:
        return self._result_model(
            endpoint=endpoint,
            params=params,
            base_url=self.sanitized_base_url,
            final_url=_sanitized_url(self.sanitized_base_url, endpoint, params),
            query_keys=sorted(params.keys()),
            status_code=None,
            reason_type=reason_type,
            error_class=None,
            error_message_sanitized=_sanitize_text(error_message, self.api_key),
            elapsed_ms=0,
            response_content_type=None,
            response_preview_sanitized=None,
            suggested_next_action=suggested_fix(reason_type),
            result=result,
            response_format=None,
            sample_law_count=None,
        )

    def _result_model(self, **kwargs: Any) -> MolegLiveDiagnosticResult:
        reason_type = kwargs["reason_type"]
        config = _config_detail(self.api_enabled, self.live_test_enabled, self.base_url, self.api_key, self.timeout_seconds, self.retry_count, self.retry_backoff_seconds)
        return MolegLiveDiagnosticResult(
            live_configured=self.configured and self.live_test_enabled,
            configured=self.configured,
            live_enabled=self.live_test_enabled,
            has_secret=self.has_secret,
            key_present=config["key_present"],
            key_length=config["key_length"],
            key_fingerprint=config["key_fingerprint"],
            configured_env_names=config["configured_env_names"],
            allowed_env_names=ALLOWED_ENV_NAMES,
            base_url_configured=bool(self.base_url),
            retry_count=self.retry_count,
            backoff_seconds=self.retry_backoff_seconds,
            secret_exposed=False,
            sanitized_base_url=kwargs["base_url"],
            sanitized_endpoint=kwargs["endpoint"],
            final_url_sanitized=kwargs["final_url"],
            request_method="GET",
            query_keys=kwargs["query_keys"],
            timeout_seconds=self.timeout_seconds,
            status_code=kwargs["status_code"],
            reason_type=reason_type,
            error_class=kwargs["error_class"],
            error_message_sanitized=kwargs["error_message_sanitized"],
            elapsed_ms=kwargs["elapsed_ms"],
            response_content_type=kwargs["response_content_type"],
            response_preview_sanitized=kwargs["response_preview_sanitized"],
            suggested_next_action=kwargs["suggested_next_action"],
            reason_message=reason_message(reason_type),
            result=kwargs["result"],
            request_sanitized=True,
            raw_payload_stored=False,
            fallback_available=True,
            fallback_source_modes=FALLBACK_SOURCE_MODES,
            response_format=kwargs["response_format"],
            sample_law_count=kwargs["sample_law_count"],
        )


class MolegLiveClientUnavailable(Exception):
    pass


class MolegLiveClientError(Exception):
    pass


def parse_response(response: httpx.Response) -> ParsedMolegResponse:
    payload = _parse_response_payload(response)
    return ParsedMolegResponse(
        payload=payload,
        response_format=_response_format(response),
        sample_law_count=_sample_law_count(payload),
        first_law_identifier=_first_law_identifier(payload),
        article_count=_article_count(payload),
        law_search=parse_law_search_payload(payload),
        article_title_sample_count=_article_title_count(payload),
        article_number_sample_count=_article_number_count(payload),
    )


def _http_get(url: str, params: dict[str, str], timeout: httpx.Timeout, headers: dict[str, str], trust_env: bool) -> httpx.Response:
    try:
        return httpx.get(url, params=params, headers=headers, timeout=timeout, trust_env=trust_env, follow_redirects=True)
    except TypeError as exc:
        # Older tests monkeypatch httpx.get with the pre-Phase36 signature.
        if "unexpected keyword" not in str(exc):
            raise
        return httpx.get(url, params=params, timeout=timeout)


def redact_secret_values(value: Any, secret: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: SECRET_REDACTION if str(key) in SECRET_KEYS else redact_secret_values(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secret_values(item, secret) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value, secret)
    return value


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
        REASON_HTTP_ERROR_STATUS: "\ubc95\uc81c\ucc98 API\uac00 \uc624\ub958 HTTP \uc0c1\ud0dc \ucf54\ub4dc\ub97c \ubc18\ud658\ud588\uc2b5\ub2c8\ub2e4.",
        REASON_UNAUTHORIZED_OR_INVALID_KEY: "\ubc95\uc81c\ucc98 API \uc778\uc99d\ud0a4\uac00 \uc720\ud6a8\ud558\uc9c0 \uc54a\uac70\ub098 \uad8c\ud55c\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.",
        REASON_INVALID_REQUEST_PARAMETER: "\ubc95\uc81c\ucc98 API \uc694\uccad \ud30c\ub77c\ubbf8\ud130\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
        REASON_INVALID_RESPONSE_FORMAT: "\ubc95\uc81c\ucc98 API \uc751\ub2f5 \ud615\uc2dd\uc744 JSON/XML\ub85c \ud655\uc778\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.",
        REASON_EMPTY_RESPONSE: "\ubc95\uc81c\ucc98 API \uc751\ub2f5 \ubcf8\ubb38\uc774 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.",
        REASON_HTML_ERROR_RESPONSE: "\ubc95\uc81c\ucc98 API\uac00 HTML \uc624\ub958 \ud398\uc774\uc9c0\ub97c \ubc18\ud658\ud588\uc2b5\ub2c8\ub2e4.",
        REASON_API_ERROR_RESPONSE: "\ubc95\uc81c\ucc98 API\uac00 \uc5c5\ubb34 \uc624\ub958 \uc751\ub2f5\uc744 \ubc18\ud658\ud588\uc2b5\ub2c8\ub2e4.",
        REASON_PARSING_ERROR: "\ubc95\uc81c\ucc98 API \uc751\ub2f5 \ud30c\uc2f1 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.",
    }.get(reason_type, "\ubc95\uc81c\ucc98 API \uc5f0\uacb0 \uc624\ub958 \uc6d0\uc778\uc744 \ucd94\uac00 \ud655\uc778\ud574\uc57c \ud569\ub2c8\ub2e4.")

def suggested_fix(reason_type: str) -> str:
    return {
        REASON_OK: "search/detail/parse\uac00 \ubaa8\ub450 ok\uc774\uba74 Phase37 live ingest\ub85c \uc9c4\ud589\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
        REASON_NOT_CONFIGURED: "MOLEG_API_ENABLED, MOLEG_LIVE_TEST_ENABLED, MOLEG_API_BASE_URL, MOLEG_API_KEY \ub610\ub294 MOLEG_OC \uc124\uc815\uc744 \ud655\uc778\ud558\uc138\uc694.",
        REASON_LIVE_DISABLED: "\uc548\uc804\ud55c \ub85c\uceec \ud658\uacbd\uc5d0\uc11c\ub9cc MOLEG_LIVE_TEST_ENABLED=true\ub85c \uc124\uc815\ud558\uace0 smoke\ub97c \uc2e4\ud589\ud558\uc138\uc694.",
        REASON_INVALID_BASE_URL: "MOLEG_API_BASE_URL\uc744 http://www.law.go.kr \ub610\ub294 https://www.law.go.kr \ud615\uc2dd\uc73c\ub85c \uc124\uc815\ud558\uc138\uc694.",
        REASON_DNS_ERROR: "DNS, VPN, \ubcf4\uc548 \ud504\ub85c\uadf8\ub7a8, \uc0ac\ub0b4\ub9dd DNS \uc815\ucc45\uc744 \ud655\uc778\ud558\uc138\uc694.",
        REASON_CONNECTION_TIMEOUT: "\ub124\ud2b8\uc6cc\ud06c \uc9c0\uc5f0 \ub610\ub294 \ubc29\ud654\ubcbd\uc744 \ud655\uc778\ud558\uace0 \ud544\uc694 \uc2dc MOLEG_API_TIMEOUT_SECONDS\ub97c \ub298\ub9ac\uc138\uc694.",
        REASON_CONNECTION_REFUSED: "\ube0c\ub77c\uc6b0\uc800 \uc131\uacf5 \uc694\uccad\uacfc Python \uc694\uccad\uc758 http/https, User-Agent, trust_env, proxy \ucc28\uc774\ub97c \ud655\uc778\ud558\uc138\uc694.",
        REASON_TLS_ERROR: "\uc778\uc99d\uc11c \uc800\uc7a5\uc18c, SSL inspection, \ubcf4\uc548 \ud504\ub85d\uc2dc \uc124\uc815\uc744 \ud655\uc778\ud558\uc138\uc694.",
        REASON_PROXY_ERROR: "HTTP_PROXY/HTTPS_PROXY \uac12\uacfc \ube0c\ub77c\uc6b0\uc800 \ud504\ub85d\uc2dc \uc124\uc815 \ucc28\uc774\ub97c \ud655\uc778\ud558\uc138\uc694.",
        REASON_HTTP_ERROR_STATUS: "HTTP status\uc640 endpoint path\ub97c \ud655\uc778\ud558\uace0, \uc778\uc99d\ud0a4 \uad8c\ud55c\uc744 \uc810\uac80\ud558\uc138\uc694.",
        REASON_UNAUTHORIZED_OR_INVALID_KEY: "OC/MOLEG_API_KEY \uac12\uacfc API \uc2b9\uc778 \uc0c1\ud0dc\ub97c \ud655\uc778\ud558\uc138\uc694. \ud0a4 \uc6d0\ubb38\uc740 \uacf5\uc720\ud558\uc9c0 \ub9c8\uc138\uc694.",
        REASON_INVALID_REQUEST_PARAMETER: "target/type/query/MST/OC \ud30c\ub77c\ubbf8\ud130\uc640 endpoint\uac00 \uacf5\uc2dd \uaddc\uaca9\uacfc \ub9de\ub294\uc9c0 \ud655\uc778\ud558\uc138\uc694.",
        REASON_INVALID_RESPONSE_FORMAT: "\uc751\ub2f5 content-type\uacfc format \uc694\uccad(type=XML/HTML)\uc744 \ud655\uc778\ud558\uc138\uc694.",
        REASON_EMPTY_RESPONSE: "endpoint, query, \uc778\uc99d\ud0a4, \ub124\ud2b8\uc6cc\ud06c \uc7a5\ube44\uc758 \ube48 \uc751\ub2f5 \ucc28\ub2e8 \uc5ec\ubd80\ub97c \ud655\uc778\ud558\uc138\uc694.",
        REASON_HTML_ERROR_RESPONSE: "\ud504\ub85d\uc2dc \ucc28\ub2e8 \ud398\uc774\uc9c0 \ub610\ub294 \uc798\ubabb\ub41c endpoint \uc5ec\ubd80\ub97c \ud655\uc778\ud558\uc138\uc694.",
        REASON_API_ERROR_RESPONSE: "\ubc95\uc81c\ucc98 \uc624\ub958 \ucf54\ub4dc/\uba54\uc2dc\uc9c0\ub97c sanitized \uc9c4\ub2e8\uc73c\ub85c \ud655\uc778\ud558\uace0 \uc694\uccad \ud30c\ub77c\ubbf8\ud130\uc640 \ud0a4 \uad8c\ud55c\uc744 \uc810\uac80\ud558\uc138\uc694.",
        REASON_PARSING_ERROR: "\uc751\ub2f5 format\uc774 \ubcc0\uacbd\ub418\uc5c8\ub294\uc9c0 \ud655\uc778\ud558\uace0 parser fixture\ub97c \uac31\uc2e0\ud558\uc138\uc694.",
    }.get(reason_type, "sanitized error_class/message\uc640 \ub124\ud2b8\uc6cc\ud06c \uc815\ucc45\uc744 \ud655\uc778\ud558\uc138\uc694.")

def retryable(reason_type: str) -> bool:
    return reason_type in {REASON_DNS_ERROR, REASON_CONNECTION_TIMEOUT, REASON_CONNECTION_REFUSED, REASON_TLS_ERROR, REASON_PROXY_ERROR, REASON_HTTP_ERROR_STATUS, REASON_UNKNOWN_CONNECTION_ERROR}


def _validate_request(path: str, params: dict[str, str], base_url: str | None = None) -> str | None:
    if base_url is not None and not _valid_base_url(base_url):
        return REASON_INVALID_BASE_URL
    if path not in {MOLEG_LAW_SEARCH_PATH, MOLEG_LAW_SERVICE_PATH}:
        return REASON_INVALID_REQUEST_PARAMETER
    if not params.get("target"):
        return REASON_INVALID_REQUEST_PARAMETER
    if not params.get("type"):
        return REASON_INVALID_REQUEST_PARAMETER
    if path == MOLEG_LAW_SEARCH_PATH and not params.get("query"):
        return REASON_INVALID_REQUEST_PARAMETER
    if path == MOLEG_LAW_SERVICE_PATH and not params.get("MST"):
        return REASON_INVALID_REQUEST_PARAMETER
    if not params.get("OC"):
        return REASON_NOT_CONFIGURED
    return None


def _parse_response_payload(response: httpx.Response) -> dict[str, Any] | list[Any]:
    content_type = response.headers.get("content-type", "").lower()
    text = response.text.strip()
    if not text:
        raise MolegLiveClientError(REASON_EMPTY_RESPONSE)
    if "html" in content_type or text.lower().startswith(("<!doctype html", "<html")):
        raise MolegLiveClientError(REASON_HTML_ERROR_RESPONSE)
    if "json" in content_type or text.startswith("{") or text.startswith("["):
        try:
            return response.json()
        except ValueError as exc:
            raise MolegLiveClientError(REASON_PARSING_ERROR) from exc
    if "xml" in content_type or text.startswith("<"):
        try:
            return _xml_text_to_dict(text)
        except ElementTree.ParseError as exc:
            raise MolegLiveClientError(REASON_PARSING_ERROR) from exc
    raise MolegLiveClientError(REASON_INVALID_RESPONSE_FORMAT)


def _classify_http_response(response: httpx.Response) -> str:
    if response.status_code in {401, 403}:
        return REASON_UNAUTHORIZED_OR_INVALID_KEY
    if response.status_code == 400:
        return REASON_INVALID_REQUEST_PARAMETER
    if response.status_code >= 400:
        return REASON_HTTP_ERROR_STATUS
    return REASON_OK


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, MolegLiveClientError):
        return str(exc) or REASON_UNKNOWN_CONNECTION_ERROR
    message = str(exc).lower()
    if isinstance(exc, httpx.TimeoutException):
        return REASON_CONNECTION_TIMEOUT
    if isinstance(exc, httpx.ProxyError) or "proxy" in message:
        return REASON_PROXY_ERROR
    if isinstance(exc, httpx.ConnectError):
        if any(token in message for token in ("dns", "getaddrinfo", "name or service", "nodename", "temporary failure in name resolution")):
            return REASON_DNS_ERROR
        if "ssl" in message or "certificate" in message or "tls" in message:
            return REASON_TLS_ERROR
        if "refused" in message or "거부" in message:
            return REASON_CONNECTION_REFUSED
        if "timed out" in message or "timeout" in message:
            return REASON_CONNECTION_TIMEOUT
        return REASON_UNKNOWN_CONNECTION_ERROR
    if isinstance(exc, httpx.HTTPStatusError):
        return REASON_HTTP_ERROR_STATUS
    if isinstance(exc, httpx.HTTPError):
        if "ssl" in message or "certificate" in message or "tls" in message:
            return REASON_TLS_ERROR
        if "proxy" in message:
            return REASON_PROXY_ERROR
        return REASON_UNKNOWN_CONNECTION_ERROR
    return REASON_UNKNOWN_CONNECTION_ERROR


def _payload_has_api_error(payload: Any) -> bool:
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            lowered = {str(key).lower(): value for key, value in item.items()}
            code = lowered.get("errorcode") or lowered.get("resultcode") or lowered.get("code")
            if code is not None and str(code).strip().lower() not in {"", "0", "00", "0000", "success", "ok"}:
                return True
            if any(key in lowered for key in ("errormessage", "errmsg", "error", "error_msg")):
                return True
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def _api_error_reason(payload: Any) -> str:
    text = str(redact_secret_values(payload)).lower()
    if any(token in text for token in ("auth", "unauthor", "invalid key", "인증", "승인", "oc")):
        return REASON_UNAUTHORIZED_OR_INVALID_KEY
    if any(token in text for token in ("parameter", "param", "요청", "필수")):
        return REASON_INVALID_REQUEST_PARAMETER
    return REASON_API_ERROR_RESPONSE


def _sample_law_count(payload: Any) -> int | None:
    law_search = parse_law_search_payload(payload)
    if law_search is not None:
        return len(law_search["laws"])
    if isinstance(payload, dict):
        for key in ("law", "Law", "laws", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
            if isinstance(value, dict):
                return 1
        counts = [_sample_law_count(value) for value in payload.values()]
        counts = [count for count in counts if count is not None]
        return max(counts) if counts else None
    if isinstance(payload, list):
        return len(payload)
    return None


def _first_law_identifier(payload: Any) -> str | None:
    law_search = parse_law_search_payload(payload)
    if law_search and law_search["laws"]:
        return law_search["laws"][0].get("mst")
    for item in _walk_dicts(payload):
        for key in ("MST", "mst", "lawId", "law_id", "법령일련번호"):
            value = item.get(key)
            if value:
                return str(value).strip()
    return None


def _article_count(payload: Any) -> int | None:
    count = 0
    for item in _walk_dicts(payload):
        if any(key in item for key in ("\uc870\ubb38\ubc88\ud638", "\uc870\ubb38\uc81c\ubaa9", "articleNo", "article_no", "articleTitle")):
            count += 1
    return count or None


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            found.append(item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def _response_format(response: httpx.Response) -> str | None:
    content_type = response.headers.get("content-type", "").lower()
    text = response.text.strip()
    if "json" in content_type or text.startswith(("{", "[")):
        return "json"
    if "xml" in content_type or text.startswith("<"):
        return "xml"
    return None


def _sanitize_base_url(base_url: str) -> str | None:
    cleaned = (base_url or "").split("?", 1)[0].rstrip("/")
    return cleaned or None


def _valid_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url or "")
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def sanitized_url(base_url: str | None, endpoint: str, params: dict[str, str]) -> str | None:
    return _sanitized_url(base_url, endpoint, params)


def _sanitized_url(base_url: str | None, endpoint: str, params: dict[str, str]) -> str | None:
    if not base_url:
        return None
    safe_params = {key: SECRET_REDACTION if key in SECRET_KEYS else value for key, value in params.items()}
    return f"{urljoin(f'{base_url}/', endpoint.lstrip('/'))}?{urlencode(safe_params)}"


def _sanitize_url_text(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value)
    if not parsed.query:
        return _sanitize_text(value)
    safe_params: list[str] = []
    for part in parsed.query.split("&"):
        key = part.split("=", 1)[0]
        safe_params.append(f"{key}={SECRET_REDACTION}" if key in SECRET_KEYS else part)
    return parsed._replace(query="&".join(safe_params)).geturl()


def _safe_response_preview(value: str, secret: str | None = None) -> str:
    sanitized = _sanitize_text(value, secret) or ""
    return sanitized[:MAX_RESPONSE_PREVIEW_CHARS]


def _sanitize_text(value: str | None, secret: str | None = None) -> str | None:
    if value is None:
        return None
    sanitized = value
    if secret:
        sanitized = sanitized.replace(secret, SECRET_REDACTION)
    for env_name in ("MOLEG_API_KEY", "MOLEG_OC"):
        env_secret = os.getenv(env_name)
        if env_secret:
            sanitized = sanitized.replace(env_secret, SECRET_REDACTION)
    return sanitized


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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


def _config_detail(api_enabled: bool, live_enabled: bool, base_url: str, api_key: str, timeout_seconds: float, retry_count: int, backoff_seconds: float) -> dict[str, Any]:
    configured_env_names = [name for name in ALLOWED_ENV_NAMES if os.getenv(name) is not None]
    key_env_names = [name for name in ("MOLEG_API_KEY", "MOLEG_OC") if os.getenv(name)]
    return {
        "api_enabled": api_enabled,
        "live_enabled": live_enabled,
        "base_url_configured": bool(base_url),
        "key_present": bool(api_key),
        "key_length": len(api_key),
        "key_fingerprint": hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8] if api_key else None,
        "configured_env_names": sorted(set(configured_env_names + key_env_names)),
        "timeout_seconds": timeout_seconds,
        "retry_count": retry_count,
        "backoff_seconds": backoff_seconds,
    }

def parse_law_search_payload(payload: Any) -> dict[str, Any] | None:
    root = payload.get("LawSearch") if isinstance(payload, dict) else None
    if not isinstance(root, dict):
        return None
    result_code = _text(root.get("resultCode"))
    if result_code and result_code != "00":
        raise MolegLiveClientError(REASON_API_ERROR_RESPONSE)
    laws = root.get("law") or []
    if isinstance(laws, dict):
        laws = [laws]
    if not isinstance(laws, list):
        laws = []
    parsed_laws: list[dict[str, Any]] = []
    for item in laws:
        if not isinstance(item, dict):
            continue
        parsed_laws.append({
            "law_name": _text(item.get("\ubc95\ub839\uba85\ud55c\uae00")),
            "mst": _text(item.get("\ubc95\ub839\uc77c\ub828\ubc88\ud638")) or _text(item.get("MST")),
            "law_id": _text(item.get("\ubc95\ub839ID")),
            "promulgation_date": _text(item.get("\uacf5\ud3ec\uc77c\uc790")),
            "promulgation_no": _text(item.get("\uacf5\ud3ec\ubc88\ud638")),
            "revision_type": _text(item.get("\uc81c\uac1c\uc815\uad6c\ubd84\uba85")),
            "ministry_name": _text(item.get("\uc18c\uad00\ubd80\ucc98\uba85")),
            "law_type": _text(item.get("\ubc95\ub839\uad6c\ubd84\uba85")),
            "effective_date": _text(item.get("\uc2dc\ud589\uc77c\uc790")),
            "detail_link_sanitized": _sanitize_url_text(_text(item.get("\ubc95\ub839\uc0c1\uc138\ub9c1\ud06c"))),
        })
    return {
        "result_code": result_code,
        "result_msg": _text(root.get("resultMsg")),
        "total_cnt": _int(root.get("totalCnt")),
        "page": _int(root.get("page")),
        "num_of_rows": _int(root.get("numOfRows")),
        "laws": parsed_laws,
    }


def _article_title_count(payload: Any) -> int:
    return sum(1 for item in _walk_dicts(payload) if any(key in item for key in ("\uc870\ubb38\uc81c\ubaa9", "articleTitle", "title")))


def _article_number_count(payload: Any) -> int:
    return sum(1 for item in _walk_dicts(payload) if any(key in item for key in ("\uc870\ubb38\ubc88\ud638", "articleNo", "article_no")))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
