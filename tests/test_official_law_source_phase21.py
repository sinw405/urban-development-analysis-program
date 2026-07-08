import os

import pytest

from app.core.config import get_settings
from app.models import Law, LawArticle, ProcedureLegalReference
from app.schemas.official_law_source import (
    MATCH_STATUS_MATCHED,
    MATCH_STATUS_PARTIAL,
    MATCH_STATUS_SOURCE_ERROR,
    MATCH_STATUS_SOURCE_UNAVAILABLE,
    MATCH_STATUS_UNMATCHED,
)
from app.services.legal_reference_service import TODO_MOLEG_API_ARTICLE_CHECK
from app.services.legal_reference_verification_service import verify_candidate_reference
from app.services.official_law_source import (
    LawSourceProviderError,
    LawSourceProviderUnavailable,
    MolegOpenApiLawSourceProvider,
    MockOfficialLawSourceProvider,
)


SECRET_VALUE = "TEST_SECRET_VALUE_DO_NOT_USE"


def _reference(
    article_number_text: str = "TEST_ARTICLE_DO_NOT_USE",
    article_title: str = "TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
) -> ProcedureLegalReference:
    law = Law(
        id=991001,
        law_name="TEST_LAW_DO_NOT_USE",
        law_key="TEST_PHASE21_LAW_KEY_DO_NOT_USE",
        source="TEST_SOURCE_DO_NOT_USE",
        mapping_status="PENDING_MOLEG_API_MAPPING",
    )
    article = LawArticle(
        id=991002,
        law_id=law.id,
        article_key="TEST_PHASE21_ARTICLE_KEY_DO_NOT_USE",
        article_number_text=article_number_text,
        article_title=article_title,
        mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
    )
    return ProcedureLegalReference(
        id=991003,
        step_code="PROJECT_BASIC_REVIEW",
        law=law,
        law_article=article,
        reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
        placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
        notes_json={"reference_quality": "candidate"},
    )


class FailingProvider:
    source_type = "test_failing_source"

    def get_article_by_law_and_article(self, law_name: str, article_number_text: str):
        raise LawSourceProviderError(f"upstream failed with secret {SECRET_VALUE}")

    def get_law_metadata(self, law_name: str):
        raise LawSourceProviderError("upstream failed")

    def search_articles(self, law_name: str | None = None, keyword: str | None = None):
        raise LawSourceProviderError("upstream failed")


def test_moleg_provider_initializes_without_api_key(monkeypatch):
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    get_settings.cache_clear()

    provider = MolegOpenApiLawSourceProvider()

    assert provider.configured is False
    with pytest.raises(LawSourceProviderUnavailable):
        provider.search_articles(law_name="TEST")


def test_unconfigured_live_provider_returns_source_unavailable(monkeypatch):
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    get_settings.cache_clear()

    result = verify_candidate_reference(
        _reference(),
        provider=MolegOpenApiLawSourceProvider(),
        source_mode="live",
    )

    assert result.match_status == MATCH_STATUS_SOURCE_UNAVAILABLE
    assert result.can_promote_to_verified is False
    assert result.source_mode == "live"


def test_mock_source_phase21_keeps_matched_partial_unmatched():
    provider = MockOfficialLawSourceProvider()

    matched = verify_candidate_reference(_reference(), provider=provider)
    partial = verify_candidate_reference(
        _reference(article_number_text="TEST_PARTIAL_ARTICLE_DO_NOT_USE", article_title="ALPHA BETA"),
        provider=provider,
    )
    unmatched = verify_candidate_reference(
        _reference(article_number_text="TEST_UNKNOWN_ARTICLE_DO_NOT_USE"),
        provider=provider,
    )

    assert matched.match_status == MATCH_STATUS_MATCHED
    assert partial.match_status == MATCH_STATUS_PARTIAL
    assert unmatched.match_status == MATCH_STATUS_UNMATCHED


def test_provider_error_does_not_crash_verification_or_expose_secret():
    result = verify_candidate_reference(_reference(), provider=FailingProvider(), source_mode="live")

    assert result.match_status == MATCH_STATUS_SOURCE_ERROR
    assert result.can_promote_to_verified is False
    assert SECRET_VALUE not in result.reason
    assert SECRET_VALUE not in result.model_dump_json()


@pytest.mark.skipif(
    not (
        os.getenv("MOLEG_LIVE_TEST_ENABLED", "").lower() in {"1", "true", "yes", "on"}
        and (os.getenv("MOLEG_API_KEY") or os.getenv("MOLEG_OC"))
        and os.getenv("MOLEG_API_BASE_URL")
    ),
    reason="MOLEG live test configuration is not enabled.",
)
def test_moleg_live_smoke_normalizes_response():
    provider = MolegOpenApiLawSourceProvider()

    try:
        results = provider.search_articles(law_name="?????", keyword="?3?")
    except LawSourceProviderError as exc:
        pytest.skip(f"MOLEG live smoke returned source_error: {type(exc).__name__}")

    assert provider.configured is True
    assert isinstance(results, list)
    if results:
        assert results[0].source_type == "moleg_open_api"
        assert results[0].law_name
        assert results[0].article_number_text
