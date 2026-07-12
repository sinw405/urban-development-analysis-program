from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MATCH_STATUS_MATCHED = "matched"
MATCH_STATUS_PARTIAL = "partial"
MATCH_STATUS_UNMATCHED = "unmatched"
MATCH_STATUS_SOURCE_UNAVAILABLE = "source_unavailable"
MATCH_STATUS_SOURCE_ERROR = "source_error"

LawSourceMode = Literal[
    "mock",
    "live",
    "official_db",
    "fallback",
    "official_manual",
    "official_manual_db",
    "official_seed",
    "official_seed_db",
]


class OfficialLawMetadata(BaseModel):
    law_name: str
    effective_date: date | None = None
    source_url: str
    source_type: str = "mock_official"
    official_law_id: str | None = None
    raw_payload_redacted: dict[str, Any] | None = Field(default=None, exclude=True)
    official_document_id: int | None = None
    article_count: int | None = None
    evidence_type: str | None = None
    source_hint: str | None = None
    source_mode_detail: str | None = None


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
    source_mode_detail: str | None = None


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
    source_mode_detail: str | None = None


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
    configured: bool = False
    live_enabled: bool = False
    has_secret: bool
    key_present: bool = False
    key_length: int = 0
    key_fingerprint: str | None = None
    configured_env_names: list[str] = Field(default_factory=list)
    allowed_env_names: list[str] = Field(default_factory=list)
    base_url_configured: bool = False
    retry_count: int = 0
    backoff_seconds: float = 0.0
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
    reason_message: str | None = None
    result: str
    request_sanitized: bool = True
    raw_payload_stored: bool = False
    fallback_available: bool = True
    fallback_source_modes: list[str] = Field(default_factory=list)
    response_format: str | None = None
    sample_law_count: int | None = None


class MolegTransportDiagnosticResponse(BaseModel):
    live_configured: bool
    configured: bool = False
    live_enabled: bool = False
    has_secret: bool
    key_present: bool = False
    key_length: int = 0
    key_fingerprint: str | None = None
    configured_env_names: list[str] = Field(default_factory=list)
    allowed_env_names: list[str] = Field(default_factory=list)
    base_url_configured: bool = False
    timeout_seconds: float | None = None
    retry_count: int = 0
    backoff_seconds: float = 0.0
    secret_exposed: bool = False
    sanitized_base_url: str | None = None
    sanitized_endpoint: str
    host: str | None = None
    port: int | None = None
    scheme: str | None = None
    proxy_detected: bool = False
    dns_ok: bool | None = None
    socket_ok: bool | None = None
    tls_ok: bool | None = None
    http_ok: bool | None = None
    endpoint_ok: bool | None = None
    status_code: int | None = None
    reason_type: str
    error_class: str | None = None
    error_message_sanitized: str | None = None
    elapsed_ms: int
    suggested_next_action: str
    reason_message: str | None = None
    final_url_sanitized: str | None = None
    response_preview_sanitized: str | None = None
    request_sanitized: bool = True
    raw_payload_stored: bool = False
    fallback_available: bool = True
    fallback_source_modes: list[str] = Field(default_factory=list)



class MolegProbeResult(BaseModel):
    name: str
    status: str
    reason_type: str
    reason_message_ko: str
    sanitized_detail: dict[str, Any] = Field(default_factory=dict)
    suggested_fix: str
    retryable: bool = False
    fallback_available: bool = True


class MolegSafeDiagnosticResponse(BaseModel):
    live_enabled: bool
    configured: bool
    transport_ok: bool
    reason_type: str
    final_reason_type: str | None = None
    reason_message: str
    reason_message_ko: str | None = None
    suggested_fix: str | None = None
    retryable: bool = False
    config_probe: MolegProbeResult | None = None
    network_probe: MolegProbeResult | None = None
    search_probe: MolegProbeResult | None = None
    detail_probe: MolegProbeResult | None = None
    parse_probe: MolegProbeResult | None = None
    probe_results: list[MolegProbeResult] = Field(default_factory=list)
    search_ok: bool = False
    detail_ok: bool = False
    parse_ok: bool = False
    browser_success_metadata_present: bool = False
    browser_success_expected_laws: list[dict[str, Any]] = Field(default_factory=list)
    endpoint_matrix: list[dict[str, Any]] = Field(default_factory=list)
    selected_endpoint: str | None = None
    sanitized_request_diff: dict[str, Any] = Field(default_factory=dict)
    user_agent_applied: bool = False
    trust_env_probe: list[dict[str, Any]] = Field(default_factory=list)
    proxy_probe: dict[str, Any] = Field(default_factory=dict)
    ready_for_live_ingest: bool = False
    diagnostic_detail: dict[str, Any] = Field(default_factory=dict)
    next_action: str
    secret_exposed: bool = False
    raw_payload_stored: bool = False
    request_sanitized: bool = True
    fallback_available: bool = True
    fallback_source_modes: list[str] = Field(default_factory=list)
    checked_at: datetime
    response_format: str | None = None
    sample_law_count: int | None = None
class OfficialLawManualImportRequest(BaseModel):
    file_path: str
    query: str | None = None
    source_provider: str = "moleg_manual_upload"
    source_mode: LawSourceMode = "official_manual"


class OfficialLawManualImportResponse(BaseModel):
    status: str
    source_mode: LawSourceMode
    source_provider: str
    document_id: int | None = None
    ingest_run_id: int | None = None
    article_count: int = 0
    provider_reason: str | None = None
    reason_type: str | None = None
    error_message_sanitized: str | None = None
    secret_exposed: bool = False


class OfficialLawSeedManifest(BaseModel):
    source_provider: str
    mode: str
    law_title: str
    law_short_title: str | None = None
    law_id: str | None = None
    mst: str | None = None
    enforcement_date: str | None = None
    promulgation_date: str | None = None
    document_status: str | None = None
    source_file: str
    source_format: Literal["json", "xml"]
    expected_min_article_count: int = 1
    is_current: bool | None = None
    notes: str | None = None


class OfficialLawSeedImportRequest(BaseModel):
    manifest_path: str


class OfficialLawSeedImportResponse(BaseModel):
    success: bool
    status: str
    source_mode: LawSourceMode
    source_mode_detail: str | None = None
    document_id: int | None = None
    document_count: int = 0
    article_count: int = 0
    ingest_run_id: int | None = None
    ingest_status: str | None = None
    source_provider: str | None = None
    law_title: str | None = None
    law_id: str | None = None
    mst: str | None = None
    enforcement_date: str | None = None
    secret_exposed: bool = False
    evidence_type: str | None = None
    warnings: list[str] = Field(default_factory=list)
    reason_type: str | None = None
    error_message_sanitized: str | None = None


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
    source_modes: list[str] = Field(default_factory=list)
    manual_import_count: int = 0
    latest_manual_import_status: str | None = None
    latest_source_provider: str | None = None
    latest_mode: str | None = None
    latest_error_reason: str | None = None
    seed_import_count: int = 0
    latest_seed_import_status: str | None = None
    latest_seed_law_title: str | None = None
    latest_seed_law_id: str | None = None
    latest_seed_mst: str | None = None
    latest_seed_enforcement_date: date | None = None
    has_urban_development_law: bool = False
    has_urban_development_enforcement_decree: bool = False
    has_urban_development_enforcement_rule: bool = False
    procedure_candidate_count: int = 0
    confirmed_reference_count: int = 0
    unconfirmed_candidate_count: int = 0
    unmatched_procedure_count: int = 0
    candidate_source_modes: list[str] = Field(default_factory=list)
    latest_candidate_generated_at: datetime | None = None
    has_candidates_for_analyze_steps: bool = False
    latest_candidate_confirmed_at: datetime | None = None
    confirmable_candidate_count: int = 0
    raw_payload_storage_violation_count: int = 0
    raw_payload_storage_policy_ok: bool = True
    moleg_live_enabled: bool = False
    moleg_configured: bool = False
    moleg_transport_ok: bool = False
    moleg_reason_type: str | None = None
    moleg_final_reason_type: str | None = None
    moleg_reason_message_ko: str | None = None
    moleg_search_ok: bool = False
    moleg_detail_ok: bool = False
    moleg_parse_ok: bool = False
    moleg_browser_success_metadata_present: bool = False
    moleg_selected_endpoint: str | None = None
    moleg_ready_for_live_ingest: bool = False
    moleg_suggested_fix: str | None = None
    moleg_last_checked_at: datetime | None = None
    moleg_secret_exposed: bool = False
    moleg_raw_payload_stored: bool = False
    fallback_available: bool = True
    fallback_source_modes: list[str] = Field(default_factory=list)
    official_seed_files_count: int = 0
    official_seed_articles_count: int = 0
    official_seed_confirmed_count: int = 0
    official_seed_unconfirmed_count: int = 0
    official_seed_ready_for_manual_authoring: bool = False
    official_seed_authoring_checklist_exists: bool = False
    official_seed_review_manifest_template_exists: bool = False
    official_seed_dry_run_supported: bool = True
    official_seed_fixture_validation_supported: bool = True
    official_seed_empty_files_count: int = 0
    official_seed_validation_status: str | None = None
    official_seed_source_material_directory_exists: bool = False
    official_seed_source_intake_status: str | None = None
    official_seed_source_intake_rows: int = 0
    official_seed_ready_for_seed_generation: bool = False
    official_seed_batch1_policy_exists: bool = False
    secret_exposed: bool = False




class OfficialLawSeedFileStatus(BaseModel):
    law_key: str | None = None
    law_name: str | None = None
    law_type: str | None = None
    status: str
    article_count: int = 0
    confirmed_count: int = 0
    unconfirmed_count: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OfficialLawSeedStatusResponse(BaseModel):
    seed_directory_exists: bool
    seed_files: list[OfficialLawSeedFileStatus] = Field(default_factory=list)
    total_files: int = 0
    valid_files: int = 0
    empty_files: int = 0
    total_articles: int = 0
    confirmed_articles: int = 0
    unconfirmed_articles: int = 0
    validation_status: str
    raw_payload_policy_ok: bool = True
    secret_exposed: bool = False
    ready_for_manual_authoring: bool = False
    authoring_checklist_exists: bool = False
    review_manifest_template_exists: bool = False
    dry_run_supported: bool = True
    fixture_validation_supported: bool = True
    total_seed_files: int = 0
    total_seed_articles: int = 0
    confirmed_seed_articles: int = 0
    unconfirmed_seed_articles: int = 0
    empty_seed_files: int = 0
    source_material_directory_exists: bool = False
    source_intake_template_exists: bool = False
    source_intake_status: str | None = None
    source_intake_rows: int = 0
    source_intake_valid_rows: int = 0
    source_intake_rejected_rows: int = 0
    ready_for_seed_generation: bool = False
    batch1_policy_exists: bool = False
    batch1_apply_supported: bool = True
    last_seed_generation_status_optional: str | None = None

class ProcedureArticleCandidateConfirmationRequest(BaseModel):
    confirmed_by: str | None = "manual_admin"
    confirmed_source: str | None = "manual_admin"
    confirmation_note: str | None = None


class ProcedureArticleCandidateUnconfirmRequest(BaseModel):
    confirmation_note: str | None = None


class ProcedureArticleCandidateActionResponse(BaseModel):
    candidate_id: int
    procedure_code: str
    is_confirmed: bool
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    confirmed_source: str | None = None
    confirmation_note: str | None = None
    status: str
    secret_exposed: bool = False

class LegalReferenceVerifyPreviewRequest(BaseModel):
    procedure_reference_ids: list[int] | None = None
    source_mode: LawSourceMode = "mock"


class LegalReferenceVerifyPreviewResponse(BaseModel):
    items: list[LegalReferenceVerificationResult]
