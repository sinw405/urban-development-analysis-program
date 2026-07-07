from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING

MOLEG_API_DISABLED = "MOLEG_API_DISABLED"


class MolegApiDisabledError(RuntimeError):
    pass


@dataclass(frozen=True)
class MolegArticleLookupRequest:
    law_name: str
    article_number_text: str | None = None
    law_key: str | None = None


@dataclass(frozen=True)
class MolegLawListRequest:
    query: str | None = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class MolegLawDetailRequest:
    law_key: str


@dataclass(frozen=True)
class MolegLookupResult:
    status: str = PENDING_MOLEG_API_MAPPING
    raw_payload: dict[str, Any] | None = None
    message: str | None = None


@dataclass(frozen=True)
class MolegArticleLookupResult:
    mapping_status: str = PENDING_MOLEG_API_MAPPING
    raw_payload: dict[str, Any] | None = None


class LegalSourceAdapter(Protocol):
    def fetch_law_list(self, request: MolegLawListRequest) -> MolegLookupResult:
        """Return a law-list payload from the legal source when integration is enabled."""

    def fetch_law_detail(self, request: MolegLawDetailRequest) -> MolegLookupResult:
        """Return a law-detail payload from the legal source when integration is enabled."""

    def lookup_article(self, request: MolegArticleLookupRequest) -> MolegArticleLookupResult:
        """Return article lookup data when a legal source integration is enabled."""


class MolegHttpAdapter:
    def __init__(self, settings: Settings | None = None, timeout_seconds: float = 10.0) -> None:
        self.settings = settings or get_settings()
        self.timeout_seconds = timeout_seconds

    def _ensure_enabled(self) -> None:
        if not self.settings.moleg_api_enabled:
            raise MolegApiDisabledError("MOLEG_API_ENABLED is false. Network calls are disabled.")
        if not self.settings.moleg_api_base_url:
            raise MolegApiDisabledError("MOLEG_API_BASE_URL is not configured.")
        if not self.settings.moleg_api_key:
            raise MolegApiDisabledError("MOLEG_API_KEY is not configured.")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self._ensure_enabled()
        url = f"{self.settings.moleg_api_base_url.rstrip('/')}/{path.lstrip('/')}"
        request_params = {**params, "api_key": self.settings.moleg_api_key}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(url, params=request_params)
            response.raise_for_status()
            return response.json()

    def fetch_law_list(self, request: MolegLawListRequest) -> MolegLookupResult:
        payload = self._get(
            "laws",
            {
                "query": request.query,
                "page": request.page,
                "page_size": request.page_size,
            },
        )
        return MolegLookupResult(raw_payload=payload)

    def fetch_law_detail(self, request: MolegLawDetailRequest) -> MolegLookupResult:
        payload = self._get("laws/detail", {"law_key": request.law_key})
        return MolegLookupResult(raw_payload=payload)

    def lookup_article(self, request: MolegArticleLookupRequest) -> MolegArticleLookupResult:
        payload = self._get(
            "laws/article",
            {
                "law_name": request.law_name,
                "article_number_text": request.article_number_text,
                "law_key": request.law_key,
            },
        )
        return MolegArticleLookupResult(raw_payload=payload)


class DisabledMolegAdapter:
    def fetch_law_list(self, request: MolegLawListRequest) -> MolegLookupResult:
        return MolegLookupResult(status=MOLEG_API_DISABLED, message="MOLEG API is disabled by configuration.")

    def fetch_law_detail(self, request: MolegLawDetailRequest) -> MolegLookupResult:
        return MolegLookupResult(status=MOLEG_API_DISABLED, message="MOLEG API is disabled by configuration.")

    def lookup_article(self, request: MolegArticleLookupRequest) -> MolegArticleLookupResult:
        return MolegArticleLookupResult(mapping_status=PENDING_MOLEG_API_MAPPING)


class StubMolegAdapter(DisabledMolegAdapter):
    pass


MolegAdapter = MolegHttpAdapter
