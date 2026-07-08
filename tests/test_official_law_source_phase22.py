import os

import httpx
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
    MOLEG_LAW_SEARCH_PATH,
    MOLEG_LAW_SERVICE_PATH,
    MolegOpenApiLawSourceProvider,
    LawSourceProviderError,
    MockOfficialLawSourceProvider,
    redact_secret_values,
)

SECRET = "TEST_PHASE22_SECRET_DO_NOT_USE"
URBAN_DEVELOPMENT_LAW = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
ARTICLE_3 = "\uc81c3\uc870"

LAW_SEARCH_FIXTURE = {
    "LawSearch": {
        "law": [
            {
                "\ubc95\ub839\uba85\ud55c\uae00": URBAN_DEVELOPMENT_LAW,
                "MST": "123456",
                "\uc2dc\ud589\uc77c\uc790": "20240101",
                "OC": SECRET,
            }
        ]
    }
}

LAW_SERVICE_FIXTURE = {
    "\ubc95\ub839": {
        "\uae30\ubcf8\uc815\ubcf4": {"\ubc95\ub839\uba85\ud55c\uae00": URBAN_DEVELOPMENT_LAW},
        "\uc870\ubb38": {
            "\uc870\ubb38\ub2e8\uc704": [
                {
                    "\uc870\ubb38\ubc88\ud638": ARTICLE_3,
                    "\uc870\ubb38\uc81c\ubaa9": "\ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815 \ub4f1",
                    "\uc870\ubb38\ub0b4\uc6a9": "\uc81c3\uc870 \ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815\uc5d0 \uad00\ud55c \ub0b4\uc6a9",
                    "request_url": f"https://www.law.go.kr/DRF/lawService.do?OC={SECRET}&MST=123456",
                }
            ]
        },
    }
}


def _reference(
    law_name: str = "TEST_LAW_DO_NOT_USE",
    article_number_text: str = "TEST_ARTICLE_DO_NOT_USE",
    article_title: str = "TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
) -> ProcedureLegalReference:
    law = Law(
        id=992001,
        law_name=law_name,
        law_key="TEST_PHASE22_LAW_KEY_DO_NOT_USE",
        source="TEST_SOURCE_DO_NOT_USE",
        mapping_status="PENDING_MOLEG_API_MAPPING",
    )
    article = LawArticle(
        id=992002,
        law_id=law.id,
        article_key="TEST_PHASE22_ARTICLE_KEY_DO_NOT_USE",
        article_number_text=article_number_text,
        article_title=article_title,
        mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
    )
    return ProcedureLegalReference(
        id=992003,
        step_code="PROJECT_BASIC_REVIEW",
        law=law,
        law_article=article,
        reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
        placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
        notes_json={"reference_quality": "candidate"},
    )


class TimeoutProvider:
    source_type = "test_timeout_provider"

    def get_article_by_law_and_article(self, law_name: str, article_number_text: str):
        raise LawSourceProviderError("timeout with secret should be hidden")

    def get_law_metadata(self, law_name: str):
        raise LawSourceProviderError("timeout")

    def search_articles(self, law_name: str | None = None, keyword: str | None = None):
        raise LawSourceProviderError("timeout")


def test_moleg_endpoint_paths_are_fixed_inside_adapter():
    assert MOLEG_LAW_SEARCH_PATH == "/DRF/lawSearch.do"
    assert MOLEG_LAW_SERVICE_PATH == "/DRF/lawService.do"


def test_api_key_missing_does_not_break_provider_initialization(monkeypatch):
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    get_settings.cache_clear()

    provider = MolegOpenApiLawSourceProvider()

    assert provider.configured is False


def test_urban_development_law_search_fixture_normalizes():
    provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)

    candidates = provider._normalize_law_candidates(LAW_SEARCH_FIXTURE)

    assert len(candidates) == 1
    assert candidates[0].law_name == URBAN_DEVELOPMENT_LAW
    assert candidates[0].official_law_id == "123456"
    assert candidates[0].source_url == "https://www.law.go.kr/DRF/lawService.do"
    assert candidates[0].raw_payload_redacted is not None
    assert SECRET not in str(candidates[0].raw_payload_redacted)


def test_law_service_fixture_normalizes_articles():
    provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)

    articles = provider._normalize_law_articles(
        LAW_SERVICE_FIXTURE,
        fallback_law_name=URBAN_DEVELOPMENT_LAW,
        fallback_law_id="123456",
    )

    assert len(articles) == 1
    assert articles[0].law_name == URBAN_DEVELOPMENT_LAW
    assert articles[0].official_law_id == "123456"
    assert articles[0].article_number_text == ARTICLE_3
    assert articles[0].article_title == "\ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815 \ub4f1"
    assert articles[0].source_url == "https://www.law.go.kr/DRF/lawService.do"
    assert articles[0].raw_payload_redacted is not None
    assert SECRET not in str(articles[0].raw_payload_redacted)
    assert "raw_payload_redacted" not in articles[0].model_dump()


def test_timeout_is_converted_to_source_error(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "get", raise_timeout)
    provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET, timeout_seconds=0.01)

    with pytest.raises(LawSourceProviderError):
        provider.search_law_candidates(URBAN_DEVELOPMENT_LAW)

    result = verify_candidate_reference(_reference(), provider=TimeoutProvider(), source_mode="live")
    assert result.match_status == MATCH_STATUS_SOURCE_ERROR
    assert result.can_promote_to_verified is False
    assert SECRET not in result.model_dump_json()


def test_secret_redaction_handles_nested_payloads():
    payload = {"OC": SECRET, "nested": {"url": f"https://example.test?OC={SECRET}"}}

    redacted = redact_secret_values(payload, SECRET)

    assert redacted["OC"] == "[REDACTED]"
    assert SECRET not in str(redacted)


def test_verify_preview_statuses_remain_compatible_without_live_api():
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
    unavailable = verify_candidate_reference(_reference(), provider=MolegOpenApiLawSourceProvider(base_url="", api_key=""), source_mode="live")
    source_error = verify_candidate_reference(_reference(), provider=TimeoutProvider(), source_mode="live")

    assert matched.match_status == MATCH_STATUS_MATCHED
    assert partial.match_status == MATCH_STATUS_PARTIAL
    assert unmatched.match_status == MATCH_STATUS_UNMATCHED
    assert unavailable.match_status == MATCH_STATUS_SOURCE_UNAVAILABLE
    assert source_error.match_status == MATCH_STATUS_SOURCE_ERROR


@pytest.mark.skipif(
    not (
        os.getenv("MOLEG_LIVE_TEST_ENABLED", "").lower() in {"1", "true", "yes", "on"}
        and (os.getenv("MOLEG_API_KEY") or os.getenv("MOLEG_OC"))
        and os.getenv("MOLEG_API_BASE_URL")
    ),
    reason="MOLEG live test configuration is not enabled.",
)
def test_moleg_live_smoke_searches_urban_development_law_and_normalizes_articles():
    provider = MolegOpenApiLawSourceProvider()

    try:
        candidates = provider.search_law_candidates(URBAN_DEVELOPMENT_LAW)
    except LawSourceProviderError as exc:
        pytest.skip(f"MOLEG live smoke returned source_error: {type(exc).__name__}")
    selected = provider._select_law_candidate(candidates, URBAN_DEVELOPMENT_LAW)

    assert selected is not None
    assert selected.official_law_id
    articles = provider.get_law_articles_by_id(selected.official_law_id, fallback_law_name=selected.law_name)
    assert isinstance(articles, list)
    if articles:
        assert articles[0].source_type == "moleg_open_api"
        assert articles[0].law_name
        assert articles[0].article_number_text
