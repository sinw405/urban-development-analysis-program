from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MATCH_STATUS_MATCHED = "matched"
MATCH_STATUS_PARTIAL = "partial"
MATCH_STATUS_UNMATCHED = "unmatched"
MATCH_STATUS_SOURCE_UNAVAILABLE = "source_unavailable"
MATCH_STATUS_SOURCE_ERROR = "source_error"

LawSourceMode = Literal["mock", "live"]


class OfficialLawMetadata(BaseModel):
    law_name: str
    effective_date: date | None = None
    source_url: str
    source_type: str = "mock_official"
    official_law_id: str | None = None
    raw_payload_redacted: dict[str, Any] | None = Field(default=None, exclude=True)


class OfficialLawArticleSnapshot(BaseModel):
    law_name: str
    article_number_text: str
    article_title: str | None = None
    article_text: str
    effective_date: date | None = None
    source_url: str
    source_type: str = "mock_official"
    official_law_id: str | None = None
    raw_payload_redacted: dict[str, Any] | None = Field(default=None, exclude=True)


class OfficialLawPagination(BaseModel):
    page: int | None = None
    page_size: int | None = None
    total_count: int | None = None
    total_pages: int | None = None


class OfficialLawCandidate(BaseModel):
    title: str
    short_title: str | None = None
    law_id: str | None = None
    mst: str | None = None
    promulgation_date: date | None = None
    enforcement_date: date | None = None
    is_current: bool | None = None
    source_url: str
    match_score: int = 0
    match_reason: str = ""
    raw_payload_redacted: dict[str, Any] | None = Field(default=None, exclude=True)


class OfficialLawArticle(BaseModel):
    article_no: str
    article_title: str | None = None
    article_text: str
    paragraphs: list[str] = Field(default_factory=list)
    source_anchor: str | None = None
    source_hint: str | None = None


class OfficialLawDocument(BaseModel):
    title: str
    law_id: str | None = None
    mst: str | None = None
    enforcement_date: date | None = None
    articles: list[OfficialLawArticle] = Field(default_factory=list)
    raw_available: bool = False
    normalized_at: datetime
    provider_reason: str = ""
    sanitized_source_url: str
    raw_payload_redacted: dict[str, Any] | None = Field(default=None, exclude=True)


class OfficialLawSearchResult(BaseModel):
    source_mode: LawSourceMode = "live"
    status: str
    query: str
    candidates: list[OfficialLawCandidate] = Field(default_factory=list)
    selected_candidate: OfficialLawCandidate | None = None
    pagination: OfficialLawPagination | None = None
    sanitized_source_url: str
    provider_reason: str = ""


class CandidateLegalReferenceSnapshot(BaseModel):
    procedure_reference_id: int
    step_code: str
    reference_quality: str
    reference_status: str
    law_name: str | None = None
    law_key: str | None = None
    article_number_text: str | None = None
    article_title: str | None = None
    article_key: str | None = None


class LegalReferenceVerificationResult(BaseModel):
    procedure_reference_id: int
    step_code: str
    match_status: str = Field(..., pattern="^(matched|partial|unmatched|source_unavailable|source_error)$")
    can_promote_to_verified: bool
    reason: str
    candidate_reference: CandidateLegalReferenceSnapshot
    official_source_snapshot: OfficialLawArticleSnapshot | None = None
    source_mode: LawSourceMode = "mock"
    provider_reason: str | None = None


class LegalReferenceVerifyPreviewRequest(BaseModel):
    procedure_reference_ids: list[int] | None = None
    source_mode: LawSourceMode = "mock"


class LegalReferenceVerifyPreviewResponse(BaseModel):
    items: list[LegalReferenceVerificationResult]
