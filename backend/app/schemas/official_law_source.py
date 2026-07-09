from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MATCH_STATUS_MATCHED = "matched"
MATCH_STATUS_PARTIAL = "partial"
MATCH_STATUS_UNMATCHED = "unmatched"
MATCH_STATUS_SOURCE_UNAVAILABLE = "source_unavailable"
MATCH_STATUS_SOURCE_ERROR = "source_error"

LawSourceMode = Literal["mock", "live", "official_db", "fallback"]


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
    official_document_id: int | None = None
    article_count: int | None = None
    evidence_type: str | None = None
    source_hint: str | None = None


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
    source_error: bool = False
    reason_type: str | None = None
    selected_candidate: OfficialLawCandidate | None = None
    document_id: int | None = None
    official_document_id: int | None = None
    article_count: int | None = None
    evidence_type: str | None = None
    sanitized_url: str | None = None
    source_hint: str | None = None
    as_of: date | None = None


class MolegDiagnosticResult(BaseModel):
    live_configured: bool
    has_secret: bool
    base_url: str | None = None
    endpoint: str
    result: str
    reason_type: str
    secret_exposed: bool = False



class MolegLiveDiagnosticResult(BaseModel):
    live_configured: bool
    has_secret: bool
    secret_exposed: bool = False
    sanitized_base_url: str | None = None
    sanitized_endpoint: str
    final_url_sanitized: str | None = None
    request_method: str = "GET"
    query_keys: list[str] = Field(default_factory=list)
    timeout_seconds: float
    status_code: int | None = None
    reason_type: str
    error_class: str | None = None
    error_message_sanitized: str | None = None
    elapsed_ms: int
    response_content_type: str | None = None
    response_preview_sanitized: str | None = None
    suggested_next_action: str
    result: str

class OfficialLawIngestPreviewRequest(BaseModel):
    query: str
    source_mode: LawSourceMode = "mock"


class OfficialLawIngestPreviewResponse(BaseModel):
    status: str
    source_mode: LawSourceMode
    selected_candidate: OfficialLawCandidate | None = None
    document_id: int | None = None
    ingest_run_id: int
    article_count: int = 0
    provider_reason: str | None = None
    secret_exposed: bool = False


class OfficialLawSnapshotStatusResponse(BaseModel):
    document_count: int
    article_count: int
    ingest_run_count: int
    latest_ingest_status: str | None = None
    source_provider: str | None = None
    last_normalized_at: datetime | None = None
    has_current_documents: bool = False


class LegalReferenceVerifyPreviewRequest(BaseModel):
    procedure_reference_ids: list[int] | None = None
    source_mode: LawSourceMode = "mock"


class LegalReferenceVerifyPreviewResponse(BaseModel):
    items: list[LegalReferenceVerificationResult]
