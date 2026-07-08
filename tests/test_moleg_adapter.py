import pytest

from app.core.config import get_settings
from app.services.moleg_adapter import (
    DisabledMolegAdapter,
    MOLEG_API_DISABLED,
    MolegApiDisabledError,
    MolegArticleLookupRequest,
    MolegHttpAdapter,
    MolegLawDetailRequest,
    MolegLawListRequest,
)
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING


def test_moleg_settings_default_to_disabled(monkeypatch):
    monkeypatch.delenv("MOLEG_API_ENABLED", raising=False)
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.moleg_api_enabled is False
    assert settings.moleg_api_configured is False
    assert settings.moleg_api_base_url == ""
    assert settings.moleg_api_key == ""


def test_disabled_moleg_adapter_does_not_call_network():
    adapter = DisabledMolegAdapter()

    law_list = adapter.fetch_law_list(MolegLawListRequest(query="TEST_LAW_DO_NOT_USE"))
    law_detail = adapter.fetch_law_detail(MolegLawDetailRequest(law_key="TEST_LAW_KEY_DO_NOT_USE"))
    article = adapter.lookup_article(MolegArticleLookupRequest(law_name="TEST_LAW_DO_NOT_USE"))

    assert law_list.status == MOLEG_API_DISABLED
    assert law_list.raw_payload is None
    assert law_detail.status == MOLEG_API_DISABLED
    assert law_detail.raw_payload is None
    assert article.mapping_status == PENDING_MOLEG_API_MAPPING
    assert article.raw_payload is None


def test_http_moleg_adapter_requires_enabled_configuration(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "false")
    monkeypatch.delenv("MOLEG_API_BASE_URL", raising=False)
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    get_settings.cache_clear()
    adapter = MolegHttpAdapter(settings=get_settings())

    with pytest.raises(MolegApiDisabledError):
        adapter.fetch_law_list(MolegLawListRequest(query="TEST_LAW_DO_NOT_USE"))


def test_http_moleg_adapter_requires_api_key_when_enabled(monkeypatch):
    monkeypatch.setenv("MOLEG_API_ENABLED", "true")
    monkeypatch.setenv("MOLEG_API_BASE_URL", "https://test.invalid")
    monkeypatch.delenv("MOLEG_API_KEY", raising=False)
    monkeypatch.delenv("MOLEG_OC", raising=False)
    get_settings.cache_clear()
    adapter = MolegHttpAdapter(settings=get_settings())

    with pytest.raises(MolegApiDisabledError):
        adapter.fetch_law_detail(MolegLawDetailRequest(law_key="TEST_LAW_KEY_DO_NOT_USE"))
