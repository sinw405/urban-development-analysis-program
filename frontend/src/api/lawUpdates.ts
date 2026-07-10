import { requestJson } from "./client";
import type { LawUpdateListResponse, MolegSafeDiagnosticResponse, OfficialLawSeedStatusResponse } from "./types";

export function listLawUpdates(): Promise<LawUpdateListResponse> {
  return requestJson<LawUpdateListResponse>("/api/law-updates");
}

export function getMolegDiagnostic(): Promise<MolegSafeDiagnosticResponse> {
  return requestJson<MolegSafeDiagnosticResponse>("/api/legal-references/moleg/diagnostic");
}

export function getOfficialLawSeedStatus(): Promise<OfficialLawSeedStatusResponse> {
  return requestJson<OfficialLawSeedStatusResponse>("/api/legal-references/official-law-seeds/status");
}
