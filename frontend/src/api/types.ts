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
  law_id: number;
  article_id: number;
  previous_version_id: number | null;
  new_version_id: number | null;
  change_type: string;
  detected_at: string;
  effective_date: string | null;
  impacted_step_codes: string[];
  status: string;
  source: string;
  metadata_json: Record<string, unknown> | null;
}

export interface LawUpdateListResponse {
  items: LawUpdateEvent[];
  since: string | null;
}

export interface OfficialLawArticleSnapshot {
  law_name: string;
  article_number_text: string;
  article_title: string | null;
  article_text: string;
  effective_date: string | null;
  source_url: string;
  source_type: "mock_official" | string;
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
  source_mode: "mock" | "live" | string;
}

export interface LegalReferenceVerifyPreviewRequest {
  procedure_reference_ids?: number[] | null;
  source_mode?: "mock" | "live";
}

export interface LegalReferenceVerifyPreviewResponse {
  items: LegalReferenceVerificationResult[];
}
