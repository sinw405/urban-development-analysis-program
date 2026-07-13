export interface AnalyzeRequest {
  project_name: string;
  location: string;
  area_square_meters: number;
  implementation_method: string;
  implementer_type: string;
  local_government: string;
  as_of?: string;
}

export interface LegalReferenceVersion {
  version_id: number;
  version_status: string;
  temporal_status: string;
  effective_date: string | null;
  source: string;
}

export interface LegalReference {
  step_code: string;
  reference_status: string;
  reference_quality: "candidate" | "verified" | "missing" | string;
  placeholder: string;
  law_id: number | null;
  law_key: string | null;
  law_mapping_status: string | null;
  article_id: number | null;
  article_key: string | null;
  article_mapping_status: string | null;
  current_version: LegalReferenceVersion | null;
  versions: LegalReferenceVersion[];
  notes: Record<string, unknown>;
}

export interface ProcedureArticleCandidate {
  id?: number | null;
  procedure_code: string;
  procedure_name: string | null;
  article_id: number | null;
  document_id: number | null;
  law_title: string;
  law_short_title: string | null;
  law_id: string | null;
  mst: string | null;
  article_no: string | null;
  article_title: string | null;
  article_anchor: string | null;
  match_method: string;
  match_score: number;
  match_status: "candidate" | "weak_candidate" | "no_match" | "needs_review" | string;
  confidence_level: "high" | "medium" | "low" | "unknown" | string;
  source_mode: string;
  source_mode_detail: string | null;
  is_confirmed: boolean;
  generated_at?: string | null;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  confirmed_source?: string | null;
  confirmation_note?: string | null;
}

export interface ProcedureStep {
  step_code: string;
  step_name: string;
  sequence: number;
  description: string;
  required_documents: string[];
  related_agencies: string[];
  estimated_duration: string;
  legal_basis_placeholder: string[];
  legal_references: LegalReference[];
  legal_reference_status: "candidate" | "verified" | "missing" | string;
  official_article_candidates: ProcedureArticleCandidate[];
  legal_reference_candidates: ProcedureArticleCandidate[];
  reference_candidate_count: number;
  reference_status: "official_candidate_available" | "no_official_candidate" | "fixture_only" | "needs_seed_data" | string;
  notes: string[];
}

export interface AssessmentItem {
  assessment_code: string | null;
  name: string;
  status: string;
  threshold: string;
  legal_basis: string;
  required_action: string;
  notes: string[];
}

export interface AnalyzeResponse {
  project_name: string;
  location: string;
  area_square_meters: number;
  implementation_method: string;
  implementer_type: string;
  local_government: string;
  as_of: string | null;
  procedures: ProcedureStep[];
  assessments: AssessmentItem[];
  warnings: string[];
  project_id: number | null;
  analysis_id: number | null;
  created_at: string | null;
}

export interface AnalysisSummary {
  analysis_id: number;
  project_id: number;
  project_name: string;
  location: string;
  area_square_meters: number;
  local_government: string;
  created_at: string;
}

export interface AnalysisListResponse {
  items: AnalysisSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AnalysisDetail {
  analysis_id: number;
  project_id: number;
  project_name: string;
  request_payload: Record<string, unknown>;
  result_payload: AnalyzeResponse;
  rule_version: string | null;
  created_at: string;
}

export interface AnalysisHistoryRow extends AnalysisSummary {
  as_of: string | null;
  procedure_count: number;
  legal_reference_count: number;
}

export interface LawUpdateEvent {
  event_id: number;
  event_kind: "legacy_law_update" | "law_change_impact" | string;
  law_id: number | string | null;
  law_name: string | null;
  article_id: number | null;
  previous_version_id: number | null;
  new_version_id: number | null;
  from_mst: string | null;
  to_mst: string | null;
  from_effective_date: string | null;
  to_effective_date: string | null;
  article_no: string | null;
  article_title: string | null;
  change_type: string;
  detected_at: string;
  effective_date: string | null;
  impacted_step_codes: string[];
  affected_procedure_code: string | null;
  affected_procedure_name: string | null;
  impact_level: string | null;
  review_status: string | null;
  mapping_status: string | null;
  impact_reason: string | null;
  official_url: string | null;
  official_url_status: string;
  applicable: boolean | null;
  status: string;
  source: string;
  metadata_json: Record<string, unknown> | null;
}
export interface LawUpdateListResponse {
  items: LawUpdateEvent[];
  since: string | null;
}


export interface OfficialLawPagination {
  page: number | null;
  page_size: number | null;
  total_count: number | null;
  total_pages: number | null;
}

export interface OfficialLawCandidate {
  title: string;
  short_title: string | null;
  law_id: string | null;
  mst: string | null;
  promulgation_date: string | null;
  enforcement_date: string | null;
  is_current: boolean | null;
  source_url: string;
  match_score: number;
  match_reason: string;
}

export interface OfficialLawArticle {
  article_no: string;
  article_title: string | null;
  article_text: string;
  paragraphs: string[];
  source_anchor: string | null;
  source_hint: string | null;
}

export interface OfficialLawDocument {
  title: string;
  law_id: string | null;
  mst: string | null;
  enforcement_date: string | null;
  articles: OfficialLawArticle[];
  raw_available: boolean;
  normalized_at: string;
  provider_reason: string;
  sanitized_source_url: string;
}

export interface OfficialLawSearchResult {
  source_mode: "mock" | "live" | "official_db" | "fallback" | "official_manual" | "official_manual_db" | "official_seed" | "official_seed_db" | string;
  status: string;
  query: string;
  candidates: OfficialLawCandidate[];
  selected_candidate: OfficialLawCandidate | null;
  pagination: OfficialLawPagination | null;
  sanitized_source_url: string;
  provider_reason: string;
}

export interface OfficialLawArticleSnapshot {
  law_name: string;
  article_number_text: string;
  article_title: string | null;
  article_text: string;
  effective_date: string | null;
  source_url: string;
  source_type: "mock_official" | string;
  official_law_id?: string | null;
}

export interface CandidateLegalReferenceSnapshot {
  procedure_reference_id: number;
  step_code: string;
  reference_quality: "candidate" | "verified" | "missing" | string;
  reference_status: string;
  law_name: string | null;
  law_key: string | null;
  article_number_text: string | null;
  article_title: string | null;
  article_key: string | null;
}

export interface LegalReferenceVerificationResult {
  procedure_reference_id: number;
  step_code: string;
  match_status: "matched" | "partial" | "unmatched" | "source_unavailable" | "source_error" | string;
  can_promote_to_verified: boolean;
  reason: string;
  candidate_reference: CandidateLegalReferenceSnapshot;
  official_source_snapshot: OfficialLawArticleSnapshot | null;
  source_mode: "mock" | "live" | "official_db" | "fallback" | "official_manual" | "official_manual_db" | "official_seed" | "official_seed_db" | string;
  source_mode_detail: string | null;
  provider_reason: string | null;
  source_error: boolean;
  reason_type: string | null;
  selected_candidate: OfficialLawCandidate | null;
  document_id: number | null;
  official_document_id: number | null;
  article_count: number | null;
  evidence_type: string | null;
  sanitized_url: string | null;
  source_hint: string | null;
  as_of: string | null;
}

export interface LegalReferenceVerifyPreviewRequest {
  procedure_reference_ids?: number[] | null;
  source_mode?: "mock" | "live" | "official_db" | "fallback" | "official_manual" | "official_manual_db" | "official_seed" | "official_seed_db";
}

export interface LegalReferenceVerifyPreviewResponse {
  items: LegalReferenceVerificationResult[];
}


export interface MolegDiagnosticResult {
  live_configured: boolean;
  has_secret: boolean;
  base_url: string | null;
  endpoint: string;
  result: string;
  reason_type: string;
  secret_exposed: boolean;
}


export interface MolegLiveDiagnosticResult {
  live_configured: boolean;
  has_secret: boolean;
  secret_exposed: boolean;
  sanitized_base_url: string | null;
  sanitized_endpoint: string;
  final_url_sanitized: string | null;
  request_method: string;
  query_keys: string[];
  timeout_seconds: number;
  status_code: number | null;
  reason_type: string;
  error_class: string | null;
  error_message_sanitized: string | null;
  elapsed_ms: number;
  response_content_type: string | null;
  response_preview_sanitized: string | null;
  suggested_next_action: string;
  result: string;
}

export interface MolegTransportDiagnosticResponse {
  live_configured: boolean;
  has_secret: boolean;
  secret_exposed: boolean;
  sanitized_base_url: string | null;
  sanitized_endpoint: string;
  host: string | null;
  port: number | null;
  scheme: string | null;
  proxy_detected: boolean;
  dns_ok: boolean | null;
  socket_ok: boolean | null;
  tls_ok: boolean | null;
  http_ok: boolean | null;
  endpoint_ok: boolean | null;
  status_code: number | null;
  reason_type: string;
  error_class: string | null;
  error_message_sanitized: string | null;
  elapsed_ms: number;
  suggested_next_action: string;
  final_url_sanitized: string | null;
  response_preview_sanitized: string | null;
}

export interface OfficialLawManualImportRequest {
  file_path: string;
  query?: string | null;
  source_provider?: string;
  source_mode?: "official_manual" | "official_manual_db" | "official_seed" | "official_seed_db" | "mock" | "live" | "official_db" | "fallback";
}

export interface OfficialLawManualImportResponse {
  status: string;
  source_mode: "official_manual" | "official_manual_db" | "official_seed" | "official_seed_db" | "mock" | "live" | "official_db" | "fallback" | string;
  source_provider: string;
  document_id: number | null;
  ingest_run_id: number | null;
  article_count: number;
  provider_reason: string | null;
  reason_type: string | null;
  error_message_sanitized: string | null;
  secret_exposed: boolean;
}

export interface OfficialLawSeedManifest {
  source_provider: string;
  mode: string;
  law_title: string;
  law_short_title: string | null;
  law_id: string | null;
  mst: string | null;
  enforcement_date: string | null;
  promulgation_date: string | null;
  document_status: string | null;
  source_file: string;
  source_format: "json" | "xml";
  expected_min_article_count: number;
  is_current: boolean | null;
  notes: string | null;
}

export interface OfficialLawSeedImportRequest {
  manifest_path: string;
}

export interface OfficialLawSeedImportResponse {
  success: boolean;
  status: string;
  source_mode: "official_seed" | "official_seed_db" | "official_manual" | "official_manual_db" | "mock" | "live" | "official_db" | "fallback" | string;
  source_mode_detail: string | null;
  document_id: number | null;
  document_count: number;
  article_count: number;
  ingest_run_id: number | null;
  ingest_status: string | null;
  source_provider: string | null;
  law_title: string | null;
  law_id: string | null;
  mst: string | null;
  enforcement_date: string | null;
  secret_exposed: boolean;
  evidence_type: string | null;
  warnings: string[];
  reason_type: string | null;
  error_message_sanitized: string | null;
}

export interface ProcedureArticleCandidateGroup {
  procedure_code: string;
  procedure_name: string;
  candidates: ProcedureArticleCandidate[];
}

export interface ProcedureArticleCandidateResponse {
  items: ProcedureArticleCandidateGroup[];
  unmatched_steps: Array<{
    procedure_code: string;
    procedure_name: string;
    match_status: string;
  }>;
  warnings: string[];
}
export interface ProcedureArticleCandidateConfirmationRequest {
  confirmed_by?: string | null;
  confirmed_source?: string | null;
  confirmation_note?: string | null;
}

export interface ProcedureArticleCandidateUnconfirmRequest {
  confirmation_note?: string | null;
}

export interface ProcedureArticleCandidateActionResponse {
  candidate_id: number;
  procedure_code: string;
  is_confirmed: boolean;
  confirmed_at: string | null;
  confirmed_by: string | null;
  confirmed_source: string | null;
  confirmation_note: string | null;
  status: string;
  secret_exposed: boolean;
}

export interface OfficialLawIngestPreviewRequest {
  query: string;
  source_mode?: "mock" | "live" | "official_db" | "fallback" | "official_manual" | "official_manual_db" | "official_seed" | "official_seed_db";
}

export interface OfficialLawIngestPreviewResponse {
  status: string;
  source_mode: "mock" | "live" | "official_db" | "fallback" | "official_manual" | "official_manual_db" | "official_seed" | "official_seed_db" | string;
  selected_candidate: OfficialLawCandidate | null;
  document_id: number | null;
  ingest_run_id: number;
  article_count: number;
  provider_reason: string | null;
  secret_exposed: boolean;
}


export interface OfficialLawSnapshotStatusResponse {
  document_count: number;
  article_count: number;
  ingest_run_count: number;
  latest_ingest_status: string | null;
  source_provider: string | null;
  last_normalized_at: string | null;
  has_current_documents: boolean;
  source_modes?: string[];
  manual_import_count?: number;
  latest_manual_import_status?: string | null;
  seed_import_count?: number;
  latest_seed_import_status?: string | null;
  latest_seed_law_title?: string | null;
  latest_seed_law_id?: string | null;
  latest_seed_mst?: string | null;
  latest_seed_enforcement_date?: string | null;
  has_urban_development_law?: boolean;
  has_urban_development_enforcement_decree?: boolean;
  has_urban_development_enforcement_rule?: boolean;
  procedure_candidate_count?: number;
  confirmed_reference_count?: number;
  unconfirmed_candidate_count?: number;
  unmatched_procedure_count?: number;
  candidate_source_modes?: string[];
  latest_candidate_generated_at?: string | null;
  has_candidates_for_analyze_steps?: boolean;
  latest_candidate_confirmed_at?: string | null;
  confirmable_candidate_count?: number;
  raw_payload_storage_violation_count?: number;
  raw_payload_storage_policy_ok?: boolean;
  moleg_final_reason_type?: string | null;
  moleg_reason_message_ko?: string | null;
  moleg_search_ok?: boolean;
  moleg_detail_ok?: boolean;
  moleg_parse_ok?: boolean;
  official_seed_files_count?: number;
  official_seed_articles_count?: number;
  official_seed_confirmed_count?: number;
  official_seed_unconfirmed_count?: number;
  official_seed_source_material_directory_exists?: boolean;
  official_seed_source_intake_status?: string | null;
  official_seed_source_intake_rows?: number;
  official_seed_ready_for_seed_generation?: boolean;
  official_seed_batch1_policy_exists?: boolean;
  secret_exposed?: boolean;
}

export interface MolegProbeResult {
  name: string;
  status: string;
  reason_type: string;
  reason_message_ko: string;
  sanitized_detail: Record<string, unknown>;
  suggested_fix: string;
  retryable: boolean;
  fallback_available: boolean;
}

export interface MolegSafeDiagnosticResponse {
  live_enabled: boolean;
  configured: boolean;
  transport_ok: boolean;
  reason_type: string;
  final_reason_type?: string | null;
  reason_message: string;
  reason_message_ko?: string | null;
  suggested_fix?: string | null;
  retryable?: boolean;
  config_probe?: MolegProbeResult | null;
  network_probe?: MolegProbeResult | null;
  search_probe?: MolegProbeResult | null;
  detail_probe?: MolegProbeResult | null;
  parse_probe?: MolegProbeResult | null;
  probe_results?: MolegProbeResult[];
  search_ok?: boolean;
  detail_ok?: boolean;
  parse_ok?: boolean;
  browser_success_metadata_present?: boolean;
  browser_success_expected_laws?: Record<string, unknown>[];
  endpoint_matrix?: Record<string, unknown>[];
  selected_endpoint?: string | null;
  sanitized_request_diff?: Record<string, unknown>;
  user_agent_applied?: boolean;
  trust_env_probe?: Record<string, unknown>[];
  proxy_probe?: Record<string, unknown>;
  ready_for_live_ingest?: boolean;
  diagnostic_detail: Record<string, unknown>;
  next_action: string;
  secret_exposed: boolean;
  raw_payload_stored: boolean;
  request_sanitized: boolean;
  fallback_available: boolean;
  fallback_source_modes: string[];
  checked_at: string;
  response_format: string | null;
  sample_law_count: number | null;
}

export interface OfficialLawSeedFileStatus {
  law_key: string | null;
  law_name: string | null;
  law_type: string | null;
  status: string;
  article_count: number;
  confirmed_count: number;
  unconfirmed_count: number;
  errors: string[];
  warnings: string[];
}

export interface OfficialLawSeedStatusResponse {
  seed_directory_exists: boolean;
  seed_files: OfficialLawSeedFileStatus[];
  total_files: number;
  valid_files: number;
  empty_files: number;
  total_articles: number;
  confirmed_articles: number;
  unconfirmed_articles: number;
  validation_status: string;
  raw_payload_policy_ok: boolean;
  secret_exposed: boolean;
  ready_for_manual_authoring: boolean;
  authoring_checklist_exists: boolean;
  review_manifest_template_exists: boolean;
  dry_run_supported: boolean;
  fixture_validation_supported: boolean;
  total_seed_files: number;
  total_seed_articles: number;
  confirmed_seed_articles: number;
  unconfirmed_seed_articles: number;
  empty_seed_files: number;
  source_material_directory_exists: boolean;
  source_intake_template_exists: boolean;
  source_intake_status: string | null;
  source_intake_rows: number;
  source_intake_valid_rows: number;
  source_intake_rejected_rows: number;
  ready_for_seed_generation: boolean;
  batch1_policy_exists: boolean;
  batch1_apply_supported: boolean;
  last_seed_generation_status_optional: string | null;
}
