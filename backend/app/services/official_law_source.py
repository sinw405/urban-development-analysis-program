from __future__ import annotations

from datetime import date
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import OfficialLawArticleSnapshot, OfficialLawMetadata


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
        normalized_article_number = _normalize(article_number_text)
        return next(
            (
                article
                for article in self._articles
                if _normalize(article.law_name) == normalized_law_name
                and _normalize(article.article_number_text) == normalized_article_number
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
        self.base_url = (base_url if base_url is not None else settings.moleg_api_base_url).strip()
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
        articles = self.search_articles(law_name=law_name, keyword=article_number_text)
        normalized_article_number = _normalize(article_number_text)
        return next(
            (article for article in articles if _normalize(article.article_number_text) == normalized_article_number),
            None,
        )

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        articles = self.search_articles(law_name=law_name)
        if not articles:
            return None
        effective_dates = [article.effective_date for article in articles if article.effective_date is not None]
        return OfficialLawMetadata(
            law_name=articles[0].law_name,
            effective_date=min(effective_dates) if effective_dates else None,
            source_url=_safe_source_url(self.base_url),
            source_type=self.source_type,
        )

    def search_articles(
        self,
        law_name: str | None = None,
        keyword: str | None = None,
    ) -> list[OfficialLawArticleSnapshot]:
        if not self.configured:
            raise LawSourceProviderUnavailable("MOLEG API is not configured.")

        params = self._base_params()
        if law_name:
            params["query"] = law_name
        if keyword:
            params["article"] = keyword

        payload = self._request_json(path="", params=params)
        return self._normalize_articles(payload=payload, fallback_law_name=law_name, fallback_keyword=keyword)

    def _base_params(self) -> dict[str, str]:
        return {
            "OC": self.api_key,
            "type": "JSON",
        }

    def _request_json(self, path: str, params: dict[str, str]) -> dict[str, Any] | list[Any]:
        try:
            response = httpx.get(
                urljoin(self.base_url if self.base_url.endswith("/") else f"{self.base_url}/", path),
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise LawSourceProviderError("MOLEG API request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LawSourceProviderError("MOLEG API request failed.") from exc
        except ValueError as exc:
            raise LawSourceProviderError("MOLEG API returned a non-JSON response.") from exc

    def _normalize_articles(
        self,
        payload: dict[str, Any] | list[Any],
        fallback_law_name: str | None,
        fallback_keyword: str | None,
    ) -> list[OfficialLawArticleSnapshot]:
        records = _extract_record_dicts(payload)
        articles: list[OfficialLawArticleSnapshot] = []
        for record in records:
            law_name = _first_text(record, "law_name", "???", "?????", "lsNm") or fallback_law_name
            article_number = _first_text(record, "article_number_text", "????", "???????", "joNo") or fallback_keyword
            article_text = _first_text(record, "article_text", "????", "????", "joCts")
            if not law_name or not article_number or not article_text:
                continue

            articles.append(
                OfficialLawArticleSnapshot(
                    law_name=law_name,
                    article_number_text=article_number,
                    article_title=_first_text(record, "article_title", "????", "joTtl"),
                    article_text=article_text,
                    effective_date=_parse_date(_first_text(record, "effective_date", "????", "efYd")),
                    source_url=_first_text(record, "source_url", "??????", "link") or _safe_source_url(self.base_url),
                    source_type=self.source_type,
                )
            )
        return articles


def make_law_source_provider(source_mode: str = "mock") -> LawSourceProvider:
    if source_mode == "live":
        return MolegOpenApiLawSourceProvider()
    return MockOfficialLawSourceProvider()


def _extract_record_dicts(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    records: list[dict[str, Any]] = []
    stack: list[Any] = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if any(key in item for key in ("article_text", "????", "????", "joCts")):
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


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    normalized = value.replace(".", "").replace("-", "").strip()
    if len(normalized) != 8 or not normalized.isdigit():
        return None
    return date(int(normalized[:4]), int(normalized[4:6]), int(normalized[6:8]))


def _safe_source_url(base_url: str) -> str:
    return base_url.split("?", 1)[0]


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


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
        ),
        OfficialLawArticleSnapshot(
            law_name="TEST_LAW_DO_NOT_USE",
            article_number_text="TEST_PARTIAL_ARTICLE_DO_NOT_USE",
            article_title="TEST_OTHER_TITLE_DO_NOT_USE",
            article_text="TEST_PARTIAL_TEXT_DO_NOT_USE",
            effective_date=date(2099, 1, 1),
            source_url="https://mock.official.local/laws/test-law/articles/test-partial",
        ),
        OfficialLawArticleSnapshot(
            law_name="Urban Development Act Fixture",
            article_number_text="Article 3",
            article_title="Urban development zone designation",
            article_text="Mock official source fixture for urban development zone designation review.",
            effective_date=date(2026, 1, 1),
            source_url="https://mock.official.local/laws/urban-development-act/articles/3",
        ),
    ]
