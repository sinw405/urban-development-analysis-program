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
    MOLEG_JSON_TYPE,
    MOLEG_XML_TYPE,
    LawSourceProviderError,
    MockOfficialLawSourceProvider,
    MolegOpenApiLawSourceProvider,
    redact_secret_values,
)

SECRET = "TEST_PHASE23_SECRET_DO_NOT_USE"
URBAN_DEVELOPMENT_LAW = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
URBAN_DEVELOPMENT_SHORT = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
ARTICLE_3 = "\uc81c3\uc870"
ARTICLE_TITLE = "\ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815 \ub4f1"

SEARCH_FIXTURE = {
    "LawSearch": {
        "totalCnt": "2",
        "page": "1",
        "display": "20",
        "law": [
            {
                "\ubc95\ub839\uba85\ud55c\uae00": "\ub3c4\uc2dc\uac1c\ubc1c\ubc95 \uc2dc\ud589\ub839",
                "\ubc95\ub839\uc57d\uce6d\uba85": "\ub3c4\uc2dc\uac1c\ubc1c\uc2dc\ud589\ub839",
                "MST": "222222",
                "\ubc95\ub839ID": "009999",
                "\uacf5\ud3ec\uc77c\uc790": "20230101",
                "\uc2dc\ud589\uc77c\uc790": "20240101",
                "\ud604\ud589\uc5ec\ubd80": "\ud604\ud589",
            },
            {
                "\ubc95\ub839\uba85\ud55c\uae00": URBAN_DEVELOPMENT_LAW,
                "\ubc95\ub839\uc57d\uce6d\uba85": URBAN_DEVELOPMENT_SHORT,
                "MST": "111111",
                "\ubc95\ub839ID": "001234",
                "\uacf5\ud3ec\uc77c\uc790": "20220101",
                "\uc2dc\ud589\uc77c\uc790": "20240223",
                "\ud604\ud589\uc5ec\ubd80": "\ud604\ud589",
                "OC": SECRET,
            },
        ],
    }
}

DOCUMENT_FIXTURE = {
    "\ubc95\ub839": {
        "\uae30\ubcf8\uc815\ubcf4": {
            "\ubc95\ub839\uba85\ud55c\uae00": URBAN_DEVELOPMENT_LAW,
            "\ubc95\ub839ID": "001234",
            "\uc2dc\ud589\uc77c\uc790": "20240223",
        },
        "\uc870\ubb38": {
            "\uc870\ubb38\ub2e8\uc704": [
                {
                    "\uc870\ubb38\ubc88\ud638": ARTICLE_3,
                    "\uc870\ubb38\uc81c\ubaa9": ARTICLE_TITLE,
                    "\uc870\ubb38\ub0b4\uc6a9": "\uc81c3\uc870 \ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815\uc5d0 \uad00\ud55c \ub0b4\uc6a9",
                    "\ud56d": [{"\ud56d\ub0b4\uc6a9": "\u2460 \uc9c0\uc815\uad8c\uc790\ub294 \ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc744 \uc9c0\uc815\ud560 \uc218 \uc788\ub2e4."}],
                },
                {
                    "\uc870\ubb38\ubc88\ud638": "\uc81c4\uc870",
                    "\uc870\ubb38\uc81c\ubaa9": "\uac1c\ubc1c\uacc4\ud68d\uc758 \uc218\ub9bd",
                    "\uc870\ubb38\ub0b4\uc6a9": "\uc81c4\uc870 \uac1c\ubc1c\uacc4\ud68d\uc758 \uc218\ub9bd\uc5d0 \uad00\ud55c \ub0b4\uc6a9",
                },
            ]
        },
    }
}

EMPTY_SEARCH_FIXTURE = {"LawSearch": {"totalCnt": "0", "law": []}}
XML_FALLBACK_FIXTURE = {
    "LawSearch": {
        "law": {
            "\ubc95\ub839\uba85\ud55c\uae00": URBAN_DEVELOPMENT_LAW,
            "MST": "333333",
            "\uc2dc\ud589\uc77c\uc790": "20250101",
        }
    }
}


def _reference(
    law_name: str = "TEST_LAW_DO_NOT_USE",
    article_number_text: str = "TEST_ARTICLE_DO_NOT_USE",
    article_title: str = "TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
) -> ProcedureLegalReference:
    law = Law(
        id=993001,
        law_name=law_name,
        law_key="TEST_PHASE23_LAW_KEY_DO_NOT_USE",
        source="TEST_SOURCE_DO_NOT_USE",
        mapping_status="PENDING_MOLEG_API_MAPPING",
    )
    article = LawArticle(
        id=993002,
        law_id=law.id,
        article_key="TEST_PHASE23_ARTICLE_KEY_DO_NOT_USE",
        article_number_text=article_number_text,
        article_title=article_title,
        mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
    )
    return ProcedureLegalReference(
        id=993003,
        step_code="PROJECT_BASIC_REVIEW",
        law=law,
        law_article=article,
        reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
        placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
        notes_json={"reference_quality": "candidate"},
    )


class ErrorProvider:
    source_type = "test_error_provider"

    def get_article_by_law_and_article(self, law_name: str, article_number_text: str):
        raise LawSourceProviderError("source failed with hidden secret")

    def get_law_metadata(self, law_name: str):
        raise LawSourceProviderError("source failed")

    def search_articles(self, law_name: str | None = None, keyword: str | None = None):
        raise LawSourceProviderError("source failed")


def test_api_key_missing_does_not_break_provider_initialization(monkeypatch):
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    get_settings.cache_clear()

    provider = MolegOpenApiLawSourceProvider()

    assert provider.configured is False


def test_urban_development_search_fixture_normalizes_and_ranks_selected_candidate():
    provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)

    result = provider._normalize_law_search_result(SEARCH_FIXTURE, query=URBAN_DEVELOPMENT_LAW)

    assert result.status == "matched"
    assert result.pagination is not None
    assert result.pagination.total_count == 2
    assert result.pagination.total_pages == 1
    assert len(result.candidates) == 2
    assert result.selected_candidate is not None
    assert result.selected_candidate.title == URBAN_DEVELOPMENT_LAW
    assert result.selected_candidate.mst == "111111"
    assert result.selected_candidate.law_id == "001234"
    assert result.selected_candidate.enforcement_date is not None
    assert result.selected_candidate.is_current is True
    assert "exact title match" in result.selected_candidate.match_reason
    assert SECRET not in str(result.selected_candidate.raw_payload_redacted)


def test_empty_search_fixture_returns_unmatched_with_pagination():
    provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)

    result = provider._normalize_law_search_result(EMPTY_SEARCH_FIXTURE, query=URBAN_DEVELOPMENT_LAW)

    assert result.status == "unmatched"
    assert result.selected_candidate is None
    assert result.pagination is not None
    assert result.pagination.total_count == 0


def test_law_document_fixture_normalizes_articles_and_paragraphs():
    provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)

    document = provider._normalize_law_document(DOCUMENT_FIXTURE, fallback_title=URBAN_DEVELOPMENT_LAW, fallback_mst="111111")

    assert document.title == URBAN_DEVELOPMENT_LAW
    assert document.law_id == "001234"
    assert document.mst == "111111"
    assert document.enforcement_date is not None
    assert document.raw_available is True
    assert len(document.articles) == 2
    assert document.articles[0].article_no == ARTICLE_3
    assert document.articles[0].article_title == ARTICLE_TITLE
    assert document.articles[0].paragraphs
    assert "raw_payload_redacted" not in document.model_dump()


def test_xml_fallback_search_uses_xml_result_when_json_has_no_candidates(monkeypatch):
    provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)

    def fake_request(path: str, params: dict[str, str]):
        if params["type"] == MOLEG_JSON_TYPE:
            return EMPTY_SEARCH_FIXTURE
        assert params["type"] == MOLEG_XML_TYPE
        return XML_FALLBACK_FIXTURE

    monkeypatch.setattr(provider, "_request_payload", fake_request)

    result = provider.search_laws(URBAN_DEVELOPMENT_LAW)

    assert result.selected_candidate is not None
    assert result.selected_candidate.mst == "333333"
    assert "XML fallback" in result.provider_reason


def test_secret_redaction_and_source_error_status_are_stable():
    payload = {"OC": SECRET, "url": f"https://www.law.go.kr/DRF/lawSearch.do?OC={SECRET}"}
    redacted = redact_secret_values(payload, SECRET)
    assert SECRET not in str(redacted)

    result = verify_candidate_reference(_reference(), provider=ErrorProvider(), source_mode="live")
    assert result.match_status == MATCH_STATUS_SOURCE_ERROR
    assert SECRET not in result.model_dump_json()


def test_verify_preview_statuses_remain_compatible():
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
    source_error = verify_candidate_reference(_reference(), provider=ErrorProvider(), source_mode="live")

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
def test_moleg_live_smoke_selects_urban_development_law_and_normalizes_document():
    provider = MolegOpenApiLawSourceProvider()

    try:
        search_result = provider.search_laws(URBAN_DEVELOPMENT_LAW)
    except LawSourceProviderError as exc:
        pytest.skip(f"MOLEG live smoke returned source_error: {type(exc).__name__}")
    selected = search_result.selected_candidate

    assert selected is not None
    assert selected.mst
    document = provider.get_law_document(selected.mst, fallback_title=selected.title)
    assert document.title
    assert document.mst == selected.mst
    assert isinstance(document.articles, list)
    if document.articles:
        assert document.articles[0].article_no
