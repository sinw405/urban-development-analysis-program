import type { LegalReference, ProcedureStep } from "../api/types";
import { formatDate, formatList, formatStatus } from "../utils/formatters";
import { labelFor } from "../utils/labels";

function StatusBadge({ value }: { value: string | null | undefined }) {
  return <span className={`statusBadge status-${value ?? "unknown"}`}>{formatStatus(value)}</span>;
}

function LegalReferenceCards({ references }: { references: LegalReference[] }) {
  if (references.length === 0) {
    return <p className="emptyState">연결된 법령 근거가 없습니다.</p>;
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
              <dd>{reference.law_key ?? "-"}</dd>
              <dt>{labelFor("article_id")}</dt>
              <dd>{reference.article_id ?? "-"}</dd>
              <dt>{labelFor("article_key")}</dt>
              <dd>{reference.article_key ?? "-"}</dd>
              <dt>{labelFor("version_status")}</dt>
              <dd>{formatStatus(statusValue)}</dd>
              <dt>{labelFor("effective_date")}</dt>
              <dd>{formatDate(current?.effective_date)}</dd>
              <dt>{labelFor("source")}</dt>
              <dd>{current?.source ?? "-"}</dd>
            </dl>
          </article>
        );
      })}
    </div>
  );
}

interface ProcedureStepDetailProps {
  step: ProcedureStep;
}

export function ProcedureStepDetail({ step }: ProcedureStepDetailProps) {
  return (
    <article className="procedureDetailCard">
      <div className="cardTitle">
        <div>
          <p className="eyebrow">단계 상세</p>
          <h3>{step.step_name || "단계명 정보 없음"}</h3>
          <p className="muted"><code>{step.step_code}</code></p>
        </div>
        <span className="badge">법령 근거 {step.legal_references.length}개</span>
      </div>

      <p>{step.description || "단계 설명 정보가 없습니다."}</p>

      <dl className="definitionGrid compactDefinition">
        <dt>{labelFor("estimated_duration")}</dt>
        <dd>{step.estimated_duration || "예상 소요기간 정보가 없습니다."}</dd>
        <dt>조문 확인 상태</dt>
        <dd>{step.legal_basis_placeholder.length > 0 ? step.legal_basis_placeholder.join(", ") : "확인 필요"}</dd>
      </dl>

      <div className="detailColumns">
        <section>
          <h4>필요 서류</h4>
          <p>{formatList(step.required_documents, "등록된 필요 서류가 없습니다.")}</p>
        </section>
        <section>
          <h4>협의기관</h4>
          <p>{formatList(step.related_agencies, "등록된 협의기관 정보가 없습니다.")}</p>
        </section>
        <section>
          <h4>비고</h4>
          <p>{formatList(step.notes, "등록된 비고가 없습니다.")}</p>
        </section>
      </div>

      <section className="legalReferenceSection">
        <h4>법령 근거</h4>
        <LegalReferenceCards references={step.legal_references} />
      </section>
    </article>
  );
}
