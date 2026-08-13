import type { LegalReference, ProcedureArticleCandidate, ProcedureStep } from "../api/types";
import type { NormalizedProcedureStep } from "../utils/analysisSummary";
import { CANDIDATE_LEGAL_REFERENCE_NOTICE, legalReferenceQualityLabel } from "../utils/analysisSummary";
import { formatDate, formatList, formatStatus } from "../utils/formatters";
import { labelFor } from "../utils/labels";
import { ProcedureChecklist, type ChecklistStatus } from "./ProcedureChecklist";

function StatusBadge({ value }: { value: string | null | undefined }) {
  return <span className={`statusBadge status-${value ?? "unknown"}`}>{formatStatus(value)}</span>;
}

function qualityClass(value: string | null | undefined): string {
  if (value === "verified") return "verified";
  if (value === "candidate") return "candidate";
  return "missing";
}

function LegalReferenceCards({ references }: { references: LegalReference[] }) {
  if (references.length === 0) {
    return <p className="emptyState">근거미확인</p>;
  }

  return (
    <div className="referenceGrid">
      {references.map((reference, index) => {
        const current = reference.current_version;
        const statusValue = current?.temporal_status ?? current?.version_status ?? reference.reference_status;
        const quality = reference.reference_quality ?? "candidate";
        return (
          <article className="legalReferenceCard" key={`${reference.step_code}-${reference.article_id ?? index}`}>
            <div className="cardTitle compactTitle">
              <h4>법령 근거 {index + 1}</h4>
              <span className={`referenceQualityBadge ${qualityClass(quality)}`}>{legalReferenceQualityLabel(quality)}</span>
            </div>
            <dl className="definitionGrid">
              <dt>근거 상태</dt>
              <dd>{legalReferenceQualityLabel(quality)}</dd>
              <dt>{labelFor("law_id")}</dt>
              <dd>{reference.law_id ?? "-"}</dd>
              <dt>{labelFor("law_key")}</dt>
              <dd>{reference.law_key ?? "법령 키 확인 필요"}</dd>
              <dt>{labelFor("article_id")}</dt>
              <dd>{reference.article_id ?? "-"}</dd>
              <dt>{labelFor("article_key")}</dt>
              <dd>{reference.article_key ?? "조문 키 확인 필요"}</dd>
              <dt>{labelFor("version_status")}</dt>
              <dd><StatusBadge value={statusValue} /></dd>
              <dt>{labelFor("effective_date")}</dt>
              <dd>{formatDate(current?.effective_date)}</dd>
              <dt>{labelFor("source")}</dt>
              <dd>{current?.source ?? "출처 확인 필요"}</dd>
              <dt>연결 상태</dt>
              <dd>{reference.placeholder || reference.reference_status || "확인 필요"}</dd>
              <dt>조문 링크</dt>
              <dd>링크 확인 필요</dd>
            </dl>
          </article>
        );
      })}
    </div>
  );
}


function OfficialArticleCandidateCards({ candidates }: { candidates: ProcedureArticleCandidate[] }) {
  if (candidates.length === 0) {
    return <p className="emptyState">공식 조문 후보가 없습니다.</p>;
  }

  return (
    <div className="referenceGrid">
      {candidates.map((candidate, index) => (
        <article className="legalReferenceCard" key={`${candidate.id ?? candidate.article_id ?? index}-${candidate.procedure_code}`}>
          <div className="cardTitle compactTitle">
            <h4>{candidate.article_title ?? `조문 후보 ${index + 1}`}</h4>
            <span className={`referenceQualityBadge ${candidate.is_confirmed ? "verified" : "candidate"}`}>
              {candidate.is_confirmed ? "확정" : "검토 필요"}
            </span>
          </div>
          <dl className="definitionGrid">
            <dt>법령</dt>
            <dd>{candidate.law_title}</dd>
            <dt>조문</dt>
            <dd>{candidate.article_no ?? candidate.article_anchor ?? "확인 필요"}</dd>
            <dt>출처 구분</dt>
            <dd>{candidate.source_mode_detail ?? candidate.source_mode}</dd>
            <dt>신뢰도</dt>
            <dd>{candidate.confidence_level} / {candidate.match_score}</dd>
            <dt>확정 메모</dt>
            <dd>{candidate.confirmation_note ?? "-"}</dd>
          </dl>
        </article>
      ))}
    </div>
  );
}

interface ProcedureStepDetailProps {
  step: ProcedureStep;
  normalizedStep: NormalizedProcedureStep;
  checklistStatus: ChecklistStatus;
  onChecklistStatusChange: (status: ChecklistStatus) => void;
  asOf: string | null;
  persistenceScope: string;
}

export function ProcedureStepDetail({ step, normalizedStep, checklistStatus, onChecklistStatusChange, asOf, persistenceScope }: ProcedureStepDetailProps) {
  const storageKey = checklistKey(persistenceScope, 'step', step.step_code, dataFingerprint([step.required_documents, step.related_agencies, step.estimated_duration, step.legal_references]));
  return (
    <article className="procedureDetailCard">
      <div className="cardTitle">
        <div>
          <p className="eyebrow">단계 상세</p>
          <h3>{normalizedStep.title}</h3>
          <p className="muted"><code>{normalizedStep.stepCode}</code></p>
        </div>
        <span className={`referenceQualityBadge ${qualityClass(normalizedStep.legalReferenceQuality)}`}>{normalizedStep.legalReferenceState}</span>
      </div>

      <p>{normalizedStep.description}</p>

      {normalizedStep.legalReferenceQuality === "candidate" && (
        <div className="noticeBox compactNotice">
          {CANDIDATE_LEGAL_REFERENCE_NOTICE}
        </div>
      )}

      <ProcedureChecklist step={step} status={checklistStatus} onStatusChange={onChecklistStatusChange} storageKey={storageKey} />

      <dl className="definitionGrid compactDefinition">
        <dt>{labelFor("estimated_duration")}</dt>
        <dd>{normalizedStep.durationState}</dd>
        <dt>조문 확인 상태</dt>
        <dd>{step.legal_basis_placeholder.length > 0 ? step.legal_basis_placeholder.join(", ") : "확인 필요"}</dd>
        <dt>데이터 누락 여부</dt>
        <dd>{normalizedStep.hasMissingData ? "확인 필요 항목 있음" : "기본 데이터 연결됨"}</dd>
      </dl>

      <div className="detailColumns">
        <section>
          <h4>필요 서류</h4>
          <p>{formatList(normalizedStep.requiredDocuments, "서류 확인 필요")}</p>
        </section>
        <section>
          <h4>협의/인허가 기관</h4>
          <p>{formatList(normalizedStep.relatedAgencies, "기관 확인 필요")}</p>
        </section>
        <section>
          <h4>비고/주의사항</h4>
          <p>{formatList(normalizedStep.notes, "확인 필요")}</p>
        </section>
      </div>

      <section className="legalReferenceSection">
        <h4>공식 조문 후보</h4>
        <OfficialArticleCandidateCards candidates={step.official_article_candidates ?? []} />
      </section>

      <section className="legalReferenceSection">
        <h4>근거 법령</h4>
        <LegalReferenceCards references={step.legal_references} />
      </section>
      <GroundedLegalExplanation stepName={normalizedStep.title} asOf={asOf} />
    </article>
  );
}
import { GroundedLegalExplanation } from './GroundedLegalExplanation';
import { checklistKey, dataFingerprint } from '../utils/checklistPersistence';
