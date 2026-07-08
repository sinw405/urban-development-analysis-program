from __future__ import annotations

from datetime import date
from typing import Any, Protocol
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import OfficialLawArticleSnapshot, OfficialLawMetadata

MOLEG_LAW_SEARCH_PATH = "/DRF/lawSearch.do"
MOLEG_LAW_SERVICE_PATH = "/DRF/lawService.do"
MOLEG_LAW_TARGET = "law"
MOLEG_JSON_TYPE = "JSON"
MOLEG_XML_TYPE = "XML"
SECRET_REDACTION = "[REDACTED]"
SECRET_KEYS = {"OC", "oc", "api_key", "apikey", "MOLEG_API_KEY", "MOLEG_OC"}

K_LAW_NAME_HANGUL = "\ubc95\ub839\uba85\ud55c\uae00"
K_LAW_NAME = "\ubc95\ub839\uba85"
K_LAW_ID = "\ubc95\ub839ID"
K_LAW_SERIAL_ID = "\ubc95\ub839\uc77c\ub828\ubc88\ud638"
K_EFFECTIVE_DATE = "\uc2dc\ud589\uc77c\uc790"
K_EFFECTIVE_DATE_SHORT = "\uc2dc\ud589\uc77c"
K_ARTICLE_CONTENT = "\uc870\ubb38\ub0b4\uc6a9"
K_ARTICLE_BODY = "\uc870\ubb38\ubcf8\ubb38"
K_ARTICLE_TITLE = "\uc870\ubb38\uc81c\ubaa9"
K_ARTICLE_NUMBER = "\uc870\ubb38\ubc88\ud638"
K_ARTICLE_NUMBER_TEXT = "\uc870\ubb38\ubc88\ud638\ubb38\uc790\uc5f4"


class LawSourceProviderUnavailable(Exception):
    pass


class LawSourceProviderError(Exception):
    pass


class LawSourceProvider(Protocol):
    source_type: str

    def get_article_by_law_and_article(
        self,
        law_name: str,
        article_number_text: str,
    ) -> OfficialLawArticleSnapshot | None:
        ...

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        ...

    def search_articles(
        self,
        law_name: str | None = None,
        keyword: str | None = None,
    ) -> list[OfficialLawArticleSnapshot]:
        ...


class MockOfficialLawSourceProvider:
    source_type = "mock_official"

    def __init__(self, articles: list[OfficialLawArticleSnapshot] | None = None) -> None:
        self._articles = articles if articles is not None else _default_mock_articles()

    def get_article_by_law_and_article(
        self,
        law_name: str,
        article_number_text: str,
    ) -> OfficialLawArticleSnapshot | None:
        normalized_law_name = _normalize(law_name)
        normalized_article_number = _normalize_article_number(article_number_text)
        return next(
            (
                article
                for article in self._articles
                if _normalize(article.law_name) == normalized_law_name
                and _normalize_article_number(article.article_number_text) == normalized_article_number
            ),
            None,
        )

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        normalized_law_name = _normalize(law_name)
        matched = [article for article in self._articles if _normalize(article.law_name) == normalized_law_name]
        if not matched:
            return None

        effective_dates = [article.effective_date for article in matched if article.effective_date is not None]
        return OfficialLawMetadata(
            law_name=matched[0].law_name,
            effective_date=min(effective_dates) if effective_dates else None,
            source_url=f"https://mock.official.local/laws/{_url_key(matched[0].law_name)}",
            source_type=self.source_type,
            official_law_id=matched[0].official_law_id,
        )

    def search_articles(
        self,
        law_name: str | None = None,
        keyword: str | None = None,
    ) -> list[OfficialLawArticleSnapshot]:
        normalized_law_name = _normalize(law_name) if law_name else None
        normalized_keyword = _normalize(keyword) if keyword else None

        results = self._articles
        if normalized_law_name:
            results = [article for article in results if _normalize(article.law_name) == normalized_law_name]
        if normalized_keyword:
            results = [
                article
                for article in results
                if normalized_keyword in _normalize(article.article_title or "")
                or normalized_keyword in _normalize(article.article_text)
                or normalized_keyword in _normalize(article.article_number_text)
            ]
        return list(results)


class MolegOpenApiLawSourceProvider:
    source_type = "moleg_open_api"

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

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def get_article_by_law_and_article(
        self,
        law_name: str,
        article_number_text: str,
    ) -> OfficialLawArticleSnapshot | None:
        candidates = self.search_law_candidates(law_name)
        candidate = self._select_law_candidate(candidates, law_name)
        if candidate is None:
            return None

        official_law_id = candidate.official_law_id
        if not official_law_id:
            return None

        articles = self.get_law_articles_by_id(official_law_id, fallback_law_name=candidate.law_name)
        normalized_article_number = _normalize_article_number(article_number_text)
        return next(
            (
                article
                for article in articles
                if _normalize_article_number(article.article_number_text) == normalized_article_number
                or normalized_article_number in _normalize_article_number(article.article_number_text)
            ),
            None,
        )

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        candidates = self.search_law_candidates(law_name)
        candidate = self._select_law_candidate(candidates, law_name)
        if candidate is None:
            return None
        return OfficialLawMetadata(
            law_name=candidate.law_name,
            effective_date=candidate.effective_date,
            source_url=candidate.source_url,
            source_type=self.source_type,
            official_law_id=candidate.official_law_id,
            raw_payload_redacted=candidate.raw_payload_redacted,
        )

    def search_articles(
        self,
        law_name: str | None = None,
        keyword: str | None = None,
    ) -> list[OfficialLawArticleSnapshot]:
        if not law_name:
            return []
        candidate = self._select_law_candidate(self.search_law_candidates(law_name), law_name)
        if candidate is None or not candidate.official_law_id:
            return []
        articles = self.get_law_articles_by_id(candidate.official_law_id, fallback_law_name=candidate.law_name)
        if keyword:
            normalized_keyword = _normalize(keyword)
            normalized_article_keyword = _normalize_article_number(keyword)
            articles = [
                article
                for article in articles
                if normalized_keyword in _normalize(article.article_title or "")
                or normalized_keyword in _normalize(article.article_text)
                or normalized_article_keyword in _normalize_article_number(article.article_number_text)
            ]
        return articles

    def search_law_candidates(self, query: str) -> list[OfficialLawMetadata]:
        params = self._base_params(result_type=MOLEG_JSON_TYPE)
        params.update({"target": MOLEG_LAW_TARGET, "query": query})
        payload = self._request_payload(path=MOLEG_LAW_SEARCH_PATH, params=params)
        candidates = self._normalize_law_candidates(payload)
        if candidates:
            return candidates

        xml_params = self._base_params(result_type=MOLEG_XML_TYPE)
        xml_params.update({"target": MOLEG_LAW_TARGET, "query": query})
        xml_payload = self._request_payload(path=MOLEG_LAW_SEARCH_PATH, params=xml_params)
        return self._normalize_law_candidates(xml_payload)

    def get_law_articles_by_id(self, official_law_id: str, fallback_law_name: str | None = None) -> list[OfficialLawArticleSnapshot]:
        params = self._base_params(result_type=MOLEG_JSON_TYPE)
        params.update({"target": MOLEG_LAW_TARGET, "MST": official_law_id})
        payload = self._request_payload(path=MOLEG_LAW_SERVICE_PATH, params=params)
        articles = self._normalize_law_articles(payload, fallback_law_name=fallback_law_name, fallback_law_id=official_law_id)
        if articles:
            return articles

        xml_params = self._base_params(result_type=MOLEG_XML_TYPE)
        xml_params.update({"target": MOLEG_LAW_TARGET, "MST": official_law_id})
        xml_payload = self._request_payload(path=MOLEG_LAW_SERVICE_PATH, params=xml_params)
        return self._normalize_law_articles(xml_payload, fallback_law_name=fallback_law_name, fallback_law_id=official_law_id)

    def _select_law_candidate(self, candidates: list[OfficialLawMetadata], law_name: str) -> OfficialLawMetadata | None:
        normalized_law_name = _normalize(law_name)
        return next(
            (candidate for candidate in candidates if _normalize(candidate.law_name) == normalized_law_name),
            next((candidate for candidate in candidates if normalized_law_name in _normalize(candidate.law_name)), None),
        )

    def _base_params(self, result_type: str) -> dict[str, str]:
        return {
            "OC": self.api_key,
            "type": result_type,
        }

    def _request_payload(self, path: str, params: dict[str, str]) -> dict[str, Any] | list[Any]:
        if not self.configured:
            raise LawSourceProviderUnavailable("MOLEG API is not configured.")

        try:
            response = httpx.get(
                urljoin(f"{self.base_url}/", path.lstrip("/")),
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "json" in content_type.lower() or params.get("type") == MOLEG_JSON_TYPE:
                try:
                    return response.json()
                except ValueError:
                    if params.get("type") == MOLEG_JSON_TYPE:
                        raise
            return _xml_text_to_dict(response.text)
        except httpx.TimeoutException as exc:
            raise LawSourceProviderError("MOLEG API request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LawSourceProviderError("MOLEG API request failed.") from exc
        except (ValueError, ElementTree.ParseError) as exc:
            raise LawSourceProviderError("MOLEG API response could not be parsed.") from exc

    def _normalize_law_candidates(self, payload: dict[str, Any] | list[Any]) -> list[OfficialLawMetadata]:
        records = _extract_dicts_with_any(payload, (K_LAW_NAME_HANGUL, K_LAW_NAME, "lsNm", "MST", K_LAW_ID, "ID"))
        candidates: list[OfficialLawMetadata] = []
        for record in records:
            law_name = _first_text(record, "law_name", K_LAW_NAME_HANGUL, K_LAW_NAME, "lsNm")
            official_law_id = _first_text(record, "MST", "mst", K_LAW_SERIAL_ID, K_LAW_ID, "ID", "LM", "lm")
            if not law_name or not official_law_id:
                continue
            candidates.append(
                OfficialLawMetadata(
                    law_name=law_name,
                    effective_date=_parse_date(_first_text(record, K_EFFECTIVE_DATE, K_EFFECTIVE_DATE_SHORT, "efYd", "effective_date")),
                    source_url=_safe_source_url(self.base_url, MOLEG_LAW_SERVICE_PATH),
                    source_type=self.source_type,
                    official_law_id=official_law_id,
                    raw_payload_redacted=redact_secret_values(record, self.api_key),
                )
            )
        return candidates

    def _normalize_law_articles(
        self,
        payload: dict[str, Any] | list[Any],
        fallback_law_name: str | None,
        fallback_law_id: str,
    ) -> list[OfficialLawArticleSnapshot]:
        records = _extract_dicts_with_any(payload, (K_ARTICLE_CONTENT, K_ARTICLE_BODY, K_ARTICLE_TITLE, K_ARTICLE_NUMBER, "joCts", "joNo"))
        law_name = _find_first_text(payload, K_LAW_NAME_HANGUL, K_LAW_NAME, "lsNm") or fallback_law_name
        articles: list[OfficialLawArticleSnapshot] = []
        for record in records:
            article_number = _first_text(record, K_ARTICLE_NUMBER, K_ARTICLE_NUMBER_TEXT, "joNo", "article_number_text")
            article_text = _first_text(record, K_ARTICLE_CONTENT, K_ARTICLE_BODY, "joCts", "article_text")
            if not law_name or not article_number or not article_text:
                continue
            articles.append(
                OfficialLawArticleSnapshot(
                    law_name=law_name,
                    article_number_text=article_number,
                    article_title=_first_text(record, K_ARTICLE_TITLE, "joTtl", "article_title"),
                    article_text=article_text,
                    effective_date=_parse_date(_first_text(record, K_EFFECTIVE_DATE, K_EFFECTIVE_DATE_SHORT, "efYd", "effective_date")),
                    source_url=_safe_source_url(self.base_url, MOLEG_LAW_SERVICE_PATH),
                    source_type=self.source_type,
                    official_law_id=fallback_law_id,
                    raw_payload_redacted=redact_secret_values(record, self.api_key),
                )
            )
        return articles


def make_law_source_provider(source_mode: str = "mock") -> LawSourceProvider:
    if source_mode == "live":
        return MolegOpenApiLawSourceProvider()
    return MockOfficialLawSourceProvider()


def redact_secret_values(value: Any, secret: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            key: SECRET_REDACTION if key in SECRET_KEYS else redact_secret_values(item, secret)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secret_values(item, secret) for item in value]
    if isinstance(value, str) and secret and secret and secret in value:
        return value.replace(secret, SECRET_REDACTION)
    return value


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


def _extract_dicts_with_any(payload: dict[str, Any] | list[Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    stack: list[Any] = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if any(key in item for key in keys):
                records.append(item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return records


def _first_text(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _find_first_text(payload: dict[str, Any] | list[Any], *keys: str) -> str | None:
    stack: list[Any] = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            value = _first_text(item, *keys)
            if value:
                return value
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    normalized = value.replace(".", "").replace("-", "").strip()
    if len(normalized) != 8 or not normalized.isdigit():
        return None
    return date(int(normalized[:4]), int(normalized[4:6]), int(normalized[6:8]))


def _safe_source_url(base_url: str, path: str = "") -> str:
    cleaned_base_url = base_url.split("?", 1)[0].rstrip("/")
    if not path:
        return cleaned_base_url
    return urljoin(f"{cleaned_base_url}/", path.lstrip("/"))


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _normalize_article_number(value: str) -> str:
    return _normalize(value).replace(" ", "")


def _url_key(value: str) -> str:
    return _normalize(value).replace(" ", "-")


def _default_mock_articles() -> list[OfficialLawArticleSnapshot]:
    return [
        OfficialLawArticleSnapshot(
            law_name="TEST_LAW_DO_NOT_USE",
            article_number_text="TEST_ARTICLE_DO_NOT_USE",
            article_title="TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
            article_text="TEST_VERSION_DO_NOT_USE_CURRENT",
            effective_date=date(2099, 1, 1),
            source_url="https://mock.official.local/laws/test-law/articles/test-article",
            official_law_id="TEST_MOCK_MST_DO_NOT_USE",
        ),
        OfficialLawArticleSnapshot(
            law_name="TEST_LAW_DO_NOT_USE",
            article_number_text="TEST_PARTIAL_ARTICLE_DO_NOT_USE",
            article_title="TEST_OTHER_TITLE_DO_NOT_USE",
            article_text="TEST_PARTIAL_TEXT_DO_NOT_USE",
            effective_date=date(2099, 1, 1),
            source_url="https://mock.official.local/laws/test-law/articles/test-partial",
            official_law_id="TEST_MOCK_MST_DO_NOT_USE",
        ),
        OfficialLawArticleSnapshot(
            law_name="Urban Development Act Fixture",
            article_number_text="Article 3",
            article_title="Urban development zone designation",
            article_text="Mock official source fixture for urban development zone designation review.",
            effective_date=date(2026, 1, 1),
            source_url="https://mock.official.local/laws/urban-development-act/articles/3",
            official_law_id="URBAN_DEV_FIXTURE_MST",
        ),
    ]
