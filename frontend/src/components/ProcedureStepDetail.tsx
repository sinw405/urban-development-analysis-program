import type { LegalReference, ProcedureStep } from "../api/types";
import type { NormalizedProcedureStep } from "../utils/analysisSummary";
import { formatDate, formatList, formatStatus } from "../utils/formatters";
import { labelFor } from "../utils/labels";
import { ProcedureChecklist, type ChecklistStatus } from "./ProcedureChecklist";

function StatusBadge({ value }: { value: string | null | undefined }) {
  return <span className={`statusBadge status-${value ?? "unknown"}`}>{formatStatus(value)}</span>;
}

function LegalReferenceCards({ references }: { references: LegalReference[] }) {
  if (references.length === 0) {
    return <p className="emptyState">근거 미연결</p>;
  }

  return (
    <div className="referenceGrid">
      {references.map((reference, index) => {
        const current = reference.current_version;
        const statusValue = current?.temporal_status ?? current?.version_status ?? reference.reference_status;
        return (
          <article className="legalReferenceCard" key={`${reference.step_code}-${reference.article_id ?? index}`}>
            <div className="cardTitle compactTitle">
              <h4>법령 근거 {index + 1}</h4>
              <StatusBadge value={statusValue} />
            </div>
            <dl className="definitionGrid">
              <dt>{labelFor("law_id")}</dt>
              <dd>{reference.law_id ?? "-"}</dd>
              <dt>{labelFor("law_key")}</dt>
              <dd>{reference.law_key ?? "법령 키 확인 필요"}</dd>
              <dt>{labelFor("article_id")}</dt>
              <dd>{reference.article_id ?? "-"}</dd>
              <dt>{labelFor("article_key")}</dt>
              <dd>{reference.article_key ?? "조문 키 확인 필요"}</dd>
              <dt>{labelFor("version_status")}</dt>
              <dd>{formatStatus(statusValue)}</dd>
              <dt>{labelFor("effective_date")}</dt>
              <dd>{formatDate(current?.effective_date)}</dd>
              <dt>{labelFor("source")}</dt>
              <dd>{current?.source ?? "출처 확인 필요"}</dd>
              <dt>근거 연결 상태</dt>
              <dd>{reference.placeholder || reference.reference_status || "확인 필요"}</dd>
            </dl>
          </article>
        );
      })}
    </div>
  );
}

interface ProcedureStepDetailProps {
  step: ProcedureStep;
  normalizedStep: NormalizedProcedureStep;
  checklistStatus: ChecklistStatus;
  onChecklistStatusChange: (status: ChecklistStatus) => void;
}

export function ProcedureStepDetail({ step, normalizedStep, checklistStatus, onChecklistStatusChange }: ProcedureStepDetailProps) {
  return (
    <article className="procedureDetailCard">
      <div className="cardTitle">
        <div>
          <p className="eyebrow">단계 상세</p>
          <h3>{normalizedStep.title}</h3>
          <p className="muted"><code>{normalizedStep.stepCode}</code></p>
        </div>
        <span className="badge">{normalizedStep.legalReferenceState}</span>
      </div>

      <p>{normalizedStep.description}</p>

      <ProcedureChecklist step={step} status={checklistStatus} onStatusChange={onChecklistStatusChange} />

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
          <h4>협의/담당 기관</h4>
          <p>{formatList(normalizedStep.relatedAgencies, "기관 확인 필요")}</p>
        </section>
        <section>
          <h4>비고/주의사항</h4>
          <p>{formatList(normalizedStep.notes, "확인 필요")}</p>
        </section>
      </div>

      <section className="legalReferenceSection">
        <h4>근거 법령</h4>
        <LegalReferenceCards references={step.legal_references} />
      </section>
    </article>
  );
}
