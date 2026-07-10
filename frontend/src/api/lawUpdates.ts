import { requestJson } from "./client";
import type { LawUpdateListResponse, MolegSafeDiagnosticResponse } from "./types";

export function listLawUpdates(): Promise<LawUpdateListResponse> {
  return requestJson<LawUpdateListResponse>("/api/law-updates");
}

export function getMolegDiagnostic(): Promise<MolegSafeDiagnosticResponse> {
  return requestJson<MolegSafeDiagnosticResponse>("/api/legal-references/moleg/diagnostic");
}
