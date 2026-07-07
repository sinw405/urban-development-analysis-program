from dataclasses import dataclass
from typing import Protocol

from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING


@dataclass(frozen=True)
class MolegArticleLookupRequest:
    law_name: str
    article_number_text: str | None = None
    law_key: str | None = None


@dataclass(frozen=True)
class MolegArticleLookupResult:
    mapping_status: str = PENDING_MOLEG_API_MAPPING
    raw_payload: dict[str, object] | None = None


class LegalSourceAdapter(Protocol):
    def lookup_article(self, request: MolegArticleLookupRequest) -> MolegArticleLookupResult:
        """Return article lookup data when a real legal source integration is implemented."""


class MolegAdapter:
    def lookup_article(self, request: MolegArticleLookupRequest) -> MolegArticleLookupResult:
        raise NotImplementedError("MOLEG Open API calls are deferred to Phase 3.5.")


class StubMolegAdapter:
    def lookup_article(self, request: MolegArticleLookupRequest) -> MolegArticleLookupResult:
        return MolegArticleLookupResult()
