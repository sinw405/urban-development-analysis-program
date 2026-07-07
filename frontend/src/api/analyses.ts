import { requestJson } from "./client";
import type { AnalysisDetail, AnalysisListResponse, AnalysisSummary, AnalyzeResponse } from "./types";

export interface ListAnalysesParams {
  limit?: number;
  offset?: number;
  project_name?: string;
  local_government?: string;
  sort?: "created_at_desc" | "created_at_asc";
}

function buildQuery(params: ListAnalysesParams = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function listAnalyses(params: ListAnalysesParams = {}): Promise<AnalysisListResponse> {
  return requestJson<AnalysisListResponse>(`/api/analyses${buildQuery(params)}`);
}

export function getAnalysisDetail(analysisId: number): Promise<AnalysisDetail> {
  return requestJson<AnalysisDetail>(`/api/analyses/${analysisId}`);
}

export function analysisDetailToResult(detail: AnalysisDetail): AnalyzeResponse {
  return {
    ...detail.result_payload,
    analysis_id: detail.result_payload.analysis_id ?? detail.analysis_id,
    project_id: detail.result_payload.project_id ?? detail.project_id,
    project_name: detail.result_payload.project_name ?? detail.project_name,
    created_at: detail.result_payload.created_at ?? detail.created_at
  };
}

export function summarizeAnalysis(summary: AnalysisSummary, detail: AnalysisDetail) {
  const result = analysisDetailToResult(detail);
  const procedureCount = result.procedures?.length ?? 0;
  const legalReferenceCount = (result.procedures ?? []).reduce(
    (total, step) => total + (step.legal_references?.length ?? 0),
    0
  );

  return {
    ...summary,
    as_of: result.as_of ?? null,
    procedure_count: procedureCount,
    legal_reference_count: legalReferenceCount
  };
}
