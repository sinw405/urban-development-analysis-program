import { requestJson } from "./client";
import type { CaseComparisonResponse } from "./types";

export function fetchComparisonCases(projectId: number): Promise<CaseComparisonResponse> {
  return requestJson<CaseComparisonResponse>(`/api/cases?similar_to=${encodeURIComponent(projectId)}`);
}