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
DEFAULT_LIVE_QUERY = "도시개발법"
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


class MolegLiveClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        retry_count: int | None = None,
        retry_backoff_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url if base_url is not None else settings.moleg_api_base_url).strip().rstrip("/")
        self.api_key = (api_key if api_key is not None else settings.moleg_api_key).strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.moleg_api_timeout_seconds
        self.retry_count = retry_count if retry_count is not None else int(os.getenv("MOLEG_API_RETRY_COUNT", "1") or "1")
        self.retry_backoff_seconds = retry_backoff_seconds if retry_backoff_seconds is not None else _env_float("MOLEG_API_RETRY_BACKOFF_SECONDS", 0.25)
        self.api_enabled = settings.moleg_api_enabled if api_key is None and base_url is None else True
        self.live_test_enabled = settings.moleg_live_test_enabled

    @property
    def sanitized_base_url(self) -> str | None:
        return _sanitize_base_url(self.base_url)

    @property
    def configured(self) -> bool:
        return bool(self.api_enabled and self.base_url and self.api_key and _valid_base_url(self.base_url))

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

    def diagnose_law_detail(self, mst: str) -> MolegLiveDiagnosticResult:
        return self.diagnose_request(endpoint=MOLEG_LAW_SERVICE_PATH, params=self.document_params(mst=mst), require_live=True)

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
                return httpx.get(url, params=params, timeout=httpx.Timeout(self.timeout_seconds))
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
    )


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
        REASON_OK: "법제처 API 응답이 정상적으로 확인되었습니다.",
        REASON_NOT_CONFIGURED: "법제처 API 설정이 완료되지 않았습니다.",
        REASON_LIVE_DISABLED: "법제처 API live 진단이 비활성화되어 있습니다.",
        REASON_INVALID_BASE_URL: "법제처 API base URL 형식이 올바르지 않습니다.",
        REASON_DNS_ERROR: "법제처 API 호스트 DNS 조회에 실패했습니다.",
        REASON_CONNECTION_TIMEOUT: "법제처 API 연결 시간이 초과되었습니다.",
        REASON_CONNECTION_REFUSED: "법제처 API 연결이 거부되었습니다.",
        REASON_TLS_ERROR: "법제처 API TLS 또는 인증서 연결 오류가 발생했습니다.",
        REASON_PROXY_ERROR: "프록시 설정 또는 프록시 연결 오류가 발생했습니다.",
        REASON_HTTP_ERROR_STATUS: "법제처 API가 오류 HTTP 상태 코드를 반환했습니다.",
        REASON_UNAUTHORIZED_OR_INVALID_KEY: "법제처 API 인증키가 유효하지 않거나 권한이 없습니다.",
        REASON_INVALID_REQUEST_PARAMETER: "법제처 API 요청 파라미터가 올바르지 않습니다.",
        REASON_INVALID_RESPONSE_FORMAT: "법제처 API 응답 형식을 JSON/XML로 확인할 수 없습니다.",
        REASON_EMPTY_RESPONSE: "법제처 API 응답 본문이 비어 있습니다.",
        REASON_HTML_ERROR_RESPONSE: "법제처 API가 HTML 오류 페이지를 반환했습니다.",
        REASON_API_ERROR_RESPONSE: "법제처 API가 업무 오류 응답을 반환했습니다.",
        REASON_PARSING_ERROR: "법제처 API 응답 파싱 중 오류가 발생했습니다.",
    }.get(reason_type, "법제처 API 연결 오류 원인을 추가 확인해야 합니다.")


def suggested_fix(reason_type: str) -> str:
    return {
        REASON_OK: "Live search/detail smoke가 가능하므로 Phase36 live ingest 설계를 진행할 수 있습니다.",
        REASON_NOT_CONFIGURED: "MOLEG_API_ENABLED, MOLEG_LIVE_TEST_ENABLED, MOLEG_API_BASE_URL, MOLEG_API_KEY 또는 MOLEG_OC 설정을 확인하세요.",
        REASON_LIVE_DISABLED: "안전한 로컬 환경에서만 MOLEG_LIVE_TEST_ENABLED=true로 설정한 뒤 smoke를 실행하세요.",
        REASON_INVALID_BASE_URL: "MOLEG_API_BASE_URL을 https://www.law.go.kr 형식의 scheme 포함 URL로 설정하세요.",
        REASON_DNS_ERROR: "DNS, VPN, 보안 프로그램, 사내망 DNS 정책을 확인하세요.",
        REASON_CONNECTION_TIMEOUT: "네트워크 지연/방화벽을 확인하고 필요 시 MOLEG_API_TIMEOUT_SECONDS를 늘리세요.",
        REASON_CONNECTION_REFUSED: "방화벽 또는 원격 endpoint 차단 여부를 확인하세요.",
        REASON_TLS_ERROR: "인증서 신뢰 저장소, SSL inspection, 보안 프록시 설정을 확인하세요.",
        REASON_PROXY_ERROR: "HTTP_PROXY/HTTPS_PROXY 설정과 프록시 인증 상태를 확인하세요.",
        REASON_HTTP_ERROR_STATUS: "HTTP status와 endpoint path를 확인하고, 인증키 권한을 점검하세요.",
        REASON_UNAUTHORIZED_OR_INVALID_KEY: "OC/MOLEG_API_KEY 값과 API 승인 상태를 확인하세요. 키 원문은 공유하지 마세요.",
        REASON_INVALID_REQUEST_PARAMETER: "target/type/query/MST/OC 파라미터와 endpoint가 공식 규격과 맞는지 확인하세요.",
        REASON_INVALID_RESPONSE_FORMAT: "응답 content-type과 format 요청(type=JSON/XML)을 확인하세요.",
        REASON_EMPTY_RESPONSE: "endpoint, query, 인증키, 네트워크 장비의 빈 응답 차단 여부를 확인하세요.",
        REASON_HTML_ERROR_RESPONSE: "프록시/차단 페이지 또는 잘못된 endpoint 여부를 확인하세요.",
        REASON_API_ERROR_RESPONSE: "법제처 오류 코드/메시지를 sanitized 진단으로 확인하고 요청 파라미터와 키 권한을 점검하세요.",
        REASON_PARSING_ERROR: "응답 format이 변경되었는지 확인하고 parser fixture를 갱신하세요.",
    }.get(reason_type, "sanitized error_class/message와 네트워크 정책을 확인하세요.")


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
    for item in _walk_dicts(payload):
        for key in ("MST", "mst", "lawId", "law_id", "법령일련번호"):
            value = item.get(key)
            if value:
                return str(value).strip()
    return None


def _article_count(payload: Any) -> int | None:
    count = 0
    for item in _walk_dicts(payload):
        if any(key in item for key in ("article", "Article", "조문", "조문번호", "articleNo")):
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


def _sanitized_url(base_url: str | None, endpoint: str, params: dict[str, str]) -> str | None:
    if not base_url:
        return None
    safe_params = {key: SECRET_REDACTION if key in SECRET_KEYS else value for key, value in params.items()}
    return f"{urljoin(f'{base_url}/', endpoint.lstrip('/'))}?{urlencode(safe_params)}"


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