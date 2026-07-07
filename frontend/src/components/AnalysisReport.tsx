import type { AnalyzeResponse, ProcedureStep } from "../api/types";
import type { ChecklistStatus } from "./ProcedureChecklist";
import { countLegalReferences, formatArea, formatDate, formatList } from "../utils/formatters";
import { labelFor } from "../utils/labels";

interface AnalysisReportProps {
  result: AnalyzeResponse;
  checklistStatuses: Record<string, ChecklistStatus>;
}

function getStatus(statuses: Record<string, ChecklistStatus>, stepCode: string): ChecklistStatus {
  return statuses[stepCode] ?? "미확인";
}

function countByStatus(steps: ProcedureStep[], statuses: Record<string, ChecklistStatus>, status: ChecklistStatus): number {
  return steps.filter((step) => getStatus(statuses, step.step_code) === status).length;
}

export function AnalysisReport({ result, checklistStatuses }: AnalysisReportProps) {
  const legalReferenceCount = countLegalReferences(result.procedures);
  const orderedSteps = [...result.procedures].sort((left, right) => left.sequence - right.sequence);

  return (
    <section className="analysisReport" aria-label="보고서형 분석 결과">
      <div className="reportHeader">
        <div>
          <p className="eyebrow">보고서형 요약</p>
          <h2>도시개발사업 절차 분석 보고서</h2>
          <p className="muted">브라우저 인쇄 기능으로 PDF 저장이 가능합니다. 서버 PDF 생성 기능은 아직 구현하지 않았습니다.</p>
        </div>
        <button type="button" className="printButton" onClick={() => window.print()}>인쇄하기</button>
      </div>

      <div className="noticeBox compactNotice reportNotice">
        이 보고서는 개발 검증용 화면입니다. 실제 법령 조문, 조문번호, 기준값은 아직 연동되지 않았으며 TEST_*_DO_NOT_USE 데이터는 화면 검증용입니다.
      </div>

      <dl className="reportSummaryGrid">
        <div>
          <dt>{labelFor("project_name")}</dt>
          <dd>{result.project_name || "사업명 정보 없음"}</dd>
        </div>
        <div>
          <dt>{labelFor("analysis_id")}</dt>
          <dd>{result.analysis_id ?? "-"}</dd>
        </div>
        <div>
          <dt>{labelFor("project_id")}</dt>
          <dd>{result.project_id ?? "-"}</dd>
        </div>
        <div>
          <dt>{labelFor("as_of")}</dt>
          <dd>{formatDate(result.as_of)}</dd>
        </div>
        <div>
          <dt>{labelFor("created_at")}</dt>
          <dd>{formatDate(result.created_at)}</dd>
        </div>
        <div>
          <dt>{labelFor("area_square_meters")}</dt>
          <dd>{formatArea(result.area_square_meters)}</dd>
        </div>
        <div>
          <dt>절차 단계 수</dt>
          <dd>{result.procedures.length}개</dd>
        </div>
        <div>
          <dt>법령 근거 연결 수</dt>
          <dd>{legalReferenceCount}개</dd>
        </div>
        <div>
          <dt>체크리스트 진행</dt>
          <dd>완료 {countByStatus(result.procedures, checklistStatuses, "확인완료")}개 / 확인중 {countByStatus(result.procedures, checklistStatuses, "확인중")}개</dd>
        </div>
      </dl>

      <section className="reportSection">
        <h3>사업 개요</h3>
        <dl className="definitionGrid">
          <dt>{labelFor("location")}</dt>
          <dd>{result.location || "위치 정보 없음"}</dd>
          <dt>{labelFor("implementation_method")}</dt>
          <dd>{result.implementation_method || "시행방식 정보 없음"}</dd>
          <dt>{labelFor("implementer_type")}</dt>
          <dd>{result.implementer_type || "시행자 유형 정보 없음"}</dd>
          <dt>{labelFor("local_government")}</dt>
          <dd>{result.local_government || "관할 지자체 정보 없음"}</dd>
        </dl>
      </section>

      <section className="reportSection">
        <h3>절차 로드맵 요약</h3>
        {orderedSteps.length === 0 ? (
          <p className="emptyState">표시할 절차 정보가 없습니다.</p>
        ) : (
          <ol className="reportStepList">
            {orderedSteps.map((step) => (
              <li key={step.step_code}>
                <strong>{step.sequence}. {step.step_name || "단계명 정보 없음"}</strong>
                <span>{step.step_code}</span>
                <span>법령 근거 {step.legal_references.length}개 · 체크 상태 {getStatus(checklistStatuses, step.step_code)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="reportSection">
        <h3>단계별 상세 요약</h3>
        <div className="reportStepCards">
          {orderedSteps.map((step) => (
            <article className="reportStepCard" key={step.step_code}>
              <div className="cardTitle compactTitle">
                <h4>{step.sequence}. {step.step_name || "단계명 정보 없음"}</h4>
                <span className="badge neutral">{getStatus(checklistStatuses, step.step_code)}</span>
              </div>
              <p>{step.description || "단계 설명 정보가 없습니다."}</p>
              <dl className="definitionGrid">
                <dt>{labelFor("estimated_duration")}</dt>
                <dd>{step.estimated_duration || "예상 소요기간 정보가 없습니다."}</dd>
                <dt>필요 서류</dt>
                <dd>{formatList(step.required_documents, "등록된 필요 서류가 없습니다.")}</dd>
                <dt>협의기관</dt>
                <dd>{formatList(step.related_agencies, "등록된 협의기관 정보가 없습니다.")}</dd>
                <dt>법령 근거</dt>
                <dd>{step.legal_references.length > 0 ? `${step.legal_references.length}개 연결` : "연결된 법령 근거가 없습니다."}</dd>
                <dt>체크리스트 요약</dt>
                <dd>현재 화면 기준 상태: {getStatus(checklistStatuses, step.step_code)}</dd>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="reportSection reportDisclaimer">
        <h3>참고 및 고지</h3>
        <p>본 화면은 개발 검증용 분석 결과를 보기 쉽게 정리한 자료입니다. 실제 법령 근거, 조문번호, 기준값은 후속 단계에서 법제처 연동과 전문가 검토를 거쳐 확정해야 합니다.</p>
      </section>
    </section>
  );
}
