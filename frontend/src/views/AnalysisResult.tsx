import { useState } from "react";
import { AnalysisReport } from "../components/AnalysisReport";
import { CaseComparison } from "../components/CaseComparison";
import type { ChecklistStatus } from "../components/ProcedureChecklist";
import { ProcedureRoadmap } from "../components/ProcedureRoadmap";
import type { AnalyzeResponse } from "../api/types";
import { formatStatus } from "../utils/formatters";
import { labelFor } from "../utils/labels";
import { normalizeAnalysisSummary } from "../utils/analysisSummary";

interface AnalysisResultProps {
  result: AnalyzeResponse | null;
}

function isRenderableResult(result: AnalyzeResponse): boolean {
  return Array.isArray(result.procedures) && Array.isArray(result.assessments);
}

export function AnalysisResult({ result }: AnalysisResultProps) {
  const [checklistStatuses, setChecklistStatuses] = useState<Record<string, ChecklistStatus>>({});

  if (!result) {
    return (
      <section className="emptyPanel">
        <h2>분석 결과</h2>
        <p>아직 실행된 분석 결과가 없습니다. 사업 정보를 입력한 뒤 분석을 실행하세요.</p>
      </section>
    );
  }

  if (!isRenderableResult(result)) {
    return (
      <section className="emptyPanel">
        <h2>분석 결과</h2>
        <p>저장된 분석 결과의 구조를 화면에 표시할 수 없습니다. 개발자용 원문 응답에서 데이터를 확인해 주세요.</p>
        <details className="developerDetails compactDetails">
          <summary>개발자용 원문 응답 보기</summary>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </details>
      </section>
    );
  }

  const summary = normalizeAnalysisSummary(result, checklistStatuses);
  const persistenceScope = checklistScope(result);

  function updateChecklistStatus(stepCode: string, status: ChecklistStatus) {
    setChecklistStatuses((current) => ({ ...current, [stepCode]: status }));
  }

  return (
    <section className="stack">
      <section className="panel subtle">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">분석 결과</p>
            <h2>분석 요약</h2>
          </div>
          <span className="badge neutral">{summary.createdAt}</span>
        </div>
        <dl className="summaryGrid">
          <div><dt>{labelFor("analysis_id")}</dt><dd>{summary.analysisId ?? "-"}</dd></div>
          <div><dt>{labelFor("project_name")}</dt><dd>{summary.projectName}</dd></div>
          <div><dt>{labelFor("as_of")}</dt><dd>{summary.asOf}</dd></div>
          <div><dt>전체 절차 수</dt><dd>{summary.procedureCount}개</dd></div>
          <div><dt>법령 근거 연결 수</dt><dd>{summary.legalReferenceCount}개</dd></div>
          <div><dt>근거 미연결 수</dt><dd>{summary.missingLegalReferenceCount}개</dd></div>
          <div><dt>{labelFor("area_square_meters")}</dt><dd>{summary.area}</dd></div>
          <div><dt>서류 확인 필요</dt><dd>{summary.missingDocumentCount}개 단계</dd></div>
          <div><dt>기관 확인 필요</dt><dd>{summary.missingAgencyCount}개 단계</dd></div>
        </dl>
      </section>

      <CaseComparison currentProject={result} />

      <section className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">절차 로드맵 및 체크리스트</p>
            <h2>절차 진행 흐름</h2>
            <p className="muted">절차별 근거 연결, 필요 서류, 협의기관, 기간과 실무 확인상태를 함께 표시합니다.</p>
          </div>
          <span className="badge neutral">{summary.procedureCount}개 단계</span>
        </div>
        <ProcedureRoadmap steps={result.procedures} stepStatuses={checklistStatuses} onStepStatusChange={updateChecklistStatus} asOf={result.as_of} persistenceScope={persistenceScope} />
      </section>

      <section className="panel reportPanel">
        <AnalysisReport result={result} checklistStatuses={checklistStatuses} />
      </section>

      {result.assessments.length > 0 && (
        <section className="panel">
          <h2>영향평가 placeholder</h2>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>코드</th>
                  <th>상태</th>
                  <th>기준값</th>
                  <th>법령 근거</th>
                </tr>
              </thead>
              <tbody>
                {result.assessments.map((item) => (
                  <tr key={item.assessment_code ?? item.name}>
                    <td>{item.assessment_code ?? "-"}</td>
                    <td>{formatStatus(item.status)}</td>
                    <td>{item.threshold}</td>
                    <td>{item.legal_basis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {result.assessments.length > 0 ? <section className='panel'><h2>심의·평가 확인 체크리스트</h2><div className='assessmentChecklistGrid'>{result.assessments.map(item => <AssessmentChecklist key={item.assessment_code ?? item.name} item={item} scope={persistenceScope} />)}</div></section> : null}

      <details className="developerDetails">
        <summary>개발자용 원문 응답 보기</summary>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </details>
    </section>
  );
}
import { checklistScope } from '../utils/checklistPersistence';
import { AssessmentChecklist } from '../components/AssessmentChecklist';
