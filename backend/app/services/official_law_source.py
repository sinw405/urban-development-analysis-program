from __future__ import annotations

from datetime import date
from typing import Protocol

from app.schemas.official_law_source import OfficialLawArticleSnapshot, OfficialLawMetadata


class LawSourceProvider(Protocol):
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
            law_name="도시개발법",
            article_number_text="제3조",
            article_title="도시개발구역의 지정 등",
            article_text="도시개발구역 지정 검토를 위한 mock official source fixture입니다.",
            effective_date=date(2026, 1, 1),
            source_url="https://mock.official.local/laws/urban-development-act/articles/3",
        ),
    ]
