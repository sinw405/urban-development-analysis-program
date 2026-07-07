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
