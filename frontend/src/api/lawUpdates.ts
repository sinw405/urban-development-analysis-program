import { requestJson } from "./client";
import type { LawUpdateListResponse } from "./types";

export function listLawUpdates(): Promise<LawUpdateListResponse> {
  return requestJson<LawUpdateListResponse>("/api/law-updates");
}
