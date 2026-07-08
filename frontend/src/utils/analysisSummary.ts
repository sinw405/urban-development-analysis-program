import type { AnalyzeResponse, LegalReference, ProcedureStep } from "../api/types";
import type { ChecklistStatus } from "../components/ProcedureChecklist";
import { formatArea, formatDate, formatList } from "./formatters";

export type LegalReferenceQuality = "candidate" | "verified" | "missing";

export const CANDIDATE_LEGAL_REFERENCE_NOTICE =
  "본 법령 근거는 현재 후보 데이터 기준으로 연결된 항목이며, 공식 법령 원문 및 인허가권자 확인이 필요합니다.";

export interface NormalizedLegalReference {
  lawId: number | null;
  lawKey: string;
  articleId: number | null;
  articleKey: string;
  status: string;
  quality: LegalReferenceQuality;
  qualityLabel: string;
  effectiveDate: string;
  source: string;
  placeholder: string;
}

export interface NormalizedProcedureStep {
  raw: ProcedureStep;
  stepCode: string;
  sequence: number;
  title: string;
  description: string;
  legalReferences: NormalizedLegalReference[];
  legalReferenceCount: number;
  legalReferenceQuality: LegalReferenceQuality;
  legalReferenceState: string;
  requiredDocuments: string[];
  requiredDocumentCount: number;
  requiredDocumentState: string;
  relatedAgencies: string[];
  relatedAgencyCount: number;
  relatedAgencyState: string;
  duration: string;
  durationState: string;
  notes: string[];
  notesState: string;
  checklistStatus: ChecklistStatus;
  hasMissingData: boolean;
}

export interface NormalizedAnalysisSummary {
  projectName: string;
  analysisId: number | null;
  projectId: number | null;
  location: string;
  area: string;
  implementationMethod: string;
  implementerType: string;
  localGovernment: string;
  asOf: string;
  createdAt: string;
  procedureCount: number;
  legalReferenceCount: number;
  verifiedLegalReferenceCount: number;
  candidateLegalReferenceCount: number;
  missingLegalReferenceCount: number;
  missingDocumentCount: number;
  missingAgencyCount: number;
  missingDurationCount: number;
  checklistCompleteCount: number;
  checklistProgressCount: number;
  checklistPendingCount: number;
  steps: NormalizedProcedureStep[];
  hasCandidateLegalReferences: boolean;
  missingItems: string[];
}

export function checklistStatusFor(statuses: Record<string, ChecklistStatus>, stepCode: string): ChecklistStatus {
  return statuses[stepCode] ?? "미확인";
}

export function legalReferenceQualityLabel(value: string | null | undefined): string {
  if (value === "verified") return "검증완료";
  if (value === "candidate") return "후보근거";
  return "근거미확인";
}

function textOrFallback(value: string | null | undefined, fallback: string): string {
  const trimmed = typeof value === "string" ? value.trim() : "";
  return trimmed.length > 0 ? trimmed : fallback;
}

function listOrEmpty(values: string[] | null | undefined): string[] {
  return Array.isArray(values) ? values.filter((value) => value.trim().length > 0) : [];
}

function legalReferenceQuality(reference: LegalReference): LegalReferenceQuality {
  if (reference.reference_quality === "verified") return "verified";
  if (reference.reference_quality === "missing") return "missing";
  return "candidate";
}

export function normalizeLegalReference(reference: LegalReference): NormalizedLegalReference {
  const current = reference.current_version;
  const status = current?.temporal_status ?? current?.version_status ?? reference.reference_status;
  const quality = legalReferenceQuality(reference);
  return {
    lawId: reference.law_id,
    lawKey: textOrFallback(reference.law_key, "법령 키 확인 필요"),
    articleId: reference.article_id,
    articleKey: textOrFallback(reference.article_key, "조문 키 확인 필요"),
    status: textOrFallback(status, "확인 필요"),
    quality,
    qualityLabel: legalReferenceQualityLabel(quality),
    effectiveDate: formatDate(current?.effective_date),
    source: textOrFallback(current?.source, "출처 확인 필요"),
    placeholder: textOrFallback(reference.placeholder, "확인 필요")
  };
}

export function normalizeProcedureStep(step: ProcedureStep, checklistStatus: ChecklistStatus = "미확인"): NormalizedProcedureStep {
  const legalReferences = (step.legal_references ?? []).map(normalizeLegalReference);
  const requiredDocuments = listOrEmpty(step.required_documents);
  const relatedAgencies = listOrEmpty(step.related_agencies);
  const notes = listOrEmpty(step.notes);
  const duration = textOrFallback(step.estimated_duration, "기간 확인 필요");

  const hasMissingLegalReferences = legalReferences.length === 0;
  const legalReferenceQuality: LegalReferenceQuality = hasMissingLegalReferences
    ? "missing"
    : legalReferences.some((reference) => reference.quality === "candidate")
      ? "candidate"
      : "verified";
  const hasMissingDocuments = requiredDocuments.length === 0;
  const hasMissingAgencies = relatedAgencies.length === 0;
  const hasMissingDuration = duration === "기간 확인 필요" || duration.includes("TODO");

  return {
    raw: step,
    stepCode: textOrFallback(step.step_code, "STEP_CODE_CHECK_REQUIRED"),
    sequence: step.sequence,
    title: textOrFallback(step.step_name, "단계명 확인 필요"),
    description: textOrFallback(step.description, "단계 설명 확인 필요"),
    legalReferences,
    legalReferenceCount: legalReferences.length,
    legalReferenceQuality,
    legalReferenceState: hasMissingLegalReferences ? "근거미확인" : `${legalReferenceQualityLabel(legalReferenceQuality)} ${legalReferences.length}개`,
    requiredDocuments,
    requiredDocumentCount: requiredDocuments.length,
    requiredDocumentState: hasMissingDocuments ? "서류 확인 필요" : `${requiredDocuments.length}개`,
    relatedAgencies,
    relatedAgencyCount: relatedAgencies.length,
    relatedAgencyState: hasMissingAgencies ? "기관 확인 필요" : `${relatedAgencies.length}개`,
    duration,
    durationState: hasMissingDuration ? "기간 확인 필요" : duration,
    notes,
    notesState: notes.length === 0 ? "비고 확인 필요" : formatList(notes),
    checklistStatus,
    hasMissingData: hasMissingLegalReferences || hasMissingDocuments || hasMissingAgencies || hasMissingDuration
  };
}

export function normalizeProcedureSteps(steps: ProcedureStep[], checklistStatuses: Record<string, ChecklistStatus>): NormalizedProcedureStep[] {
  return [...(steps ?? [])]
    .sort((left, right) => left.sequence - right.sequence)
    .map((step) => normalizeProcedureStep(step, checklistStatusFor(checklistStatuses, step.step_code)));
}

export function normalizeAnalysisSummary(result: AnalyzeResponse, checklistStatuses: Record<string, ChecklistStatus>): NormalizedAnalysisSummary {
  const steps = normalizeProcedureSteps(result.procedures ?? [], checklistStatuses);
  const missingLegalReferenceCount = steps.filter((step) => step.legalReferenceQuality === "missing").length;
  const verifiedLegalReferenceCount = steps.reduce(
    (total, step) => total + step.legalReferences.filter((reference) => reference.quality === "verified").length,
    0
  );
  const candidateLegalReferenceCount = steps.reduce(
    (total, step) => total + step.legalReferences.filter((reference) => reference.quality === "candidate").length,
    0
  );
  const missingDocumentCount = steps.filter((step) => step.requiredDocumentCount === 0).length;
  const missingAgencyCount = steps.filter((step) => step.relatedAgencyCount === 0).length;
  const missingDurationCount = steps.filter((step) => step.durationState === "기간 확인 필요").length;

  const missingItems: string[] = [];
  if (missingLegalReferenceCount > 0) missingItems.push(`근거미확인 단계 ${missingLegalReferenceCount}개`);
  if (missingDocumentCount > 0) missingItems.push(`서류 확인 필요 단계 ${missingDocumentCount}개`);
  if (missingAgencyCount > 0) missingItems.push(`기관 확인 필요 단계 ${missingAgencyCount}개`);
  if (missingDurationCount > 0) missingItems.push(`기간 확인 필요 단계 ${missingDurationCount}개`);

  return {
    projectName: textOrFallback(result.project_name, "사업명 확인 필요"),
    analysisId: result.analysis_id,
    projectId: result.project_id,
    location: textOrFallback(result.location, "위치 확인 필요"),
    area: formatArea(result.area_square_meters),
    implementationMethod: textOrFallback(result.implementation_method, "시행방식 확인 필요"),
    implementerType: textOrFallback(result.implementer_type, "시행자 유형 확인 필요"),
    localGovernment: textOrFallback(result.local_government, "관할 지자체 확인 필요"),
    asOf: formatDate(result.as_of),
    createdAt: formatDate(result.created_at),
    procedureCount: steps.length,
    legalReferenceCount: steps.reduce((total, step) => total + step.legalReferenceCount, 0),
    verifiedLegalReferenceCount,
    candidateLegalReferenceCount,
    missingLegalReferenceCount,
    missingDocumentCount,
    missingAgencyCount,
    missingDurationCount,
    checklistCompleteCount: steps.filter((step) => step.checklistStatus === "확인완료").length,
    checklistProgressCount: steps.filter((step) => step.checklistStatus === "확인중").length,
    checklistPendingCount: steps.filter((step) => step.checklistStatus === "미확인").length,
    steps,
    hasCandidateLegalReferences: candidateLegalReferenceCount > 0,
    missingItems
  };
}
