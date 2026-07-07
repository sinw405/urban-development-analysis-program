import { requestJson } from "./client";
import type { AnalyzeRequest, AnalyzeResponse } from "./types";

export function analyzeProject(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  return requestJson<AnalyzeResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
