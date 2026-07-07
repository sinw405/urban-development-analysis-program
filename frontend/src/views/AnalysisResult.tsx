import { ProcedureRoadmap } from "../components/ProcedureRoadmap";
import type { AnalyzeResponse } from "../api/types";
import { countLegalReferences, formatArea, formatDate, formatStatus } from "../utils/formatters";
import { labelFor } from "../utils/labels";

interface AnalysisResultProps {
  result: AnalyzeResponse | null;
}

function isRenderableResult(result: AnalyzeResponse): boolean {
  return Array.isArray(result.procedures) && Array.isArray(result.assessments);
}

export function AnalysisResult({ result }: AnalysisResultProps) {
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

  const legalReferenceCount = countLegalReferences(result.procedures);

  return (
    <section className="stack">
      <section className="panel subtle">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">분석 결과</p>
            <h2>분석 요약</h2>
          </div>
          <span className="badge neutral">{result.created_at ?? "생성 시각 확인 필요"}</span>
        </div>
        <dl className="summaryGrid">
          <div>
            <dt>{labelFor("analysis_id")}</dt>
            <dd>{result.analysis_id ?? "-"}</dd>
          </div>
          <div>
            <dt>{labelFor("project_name")}</dt>
            <dd>{result.project_name}</dd>
          </div>
          <div>
            <dt>{labelFor("as_of")}</dt>
            <dd>{formatDate(result.as_of)}</dd>
          </div>
          <div>
            <dt>생성된 절차 수</dt>
            <dd>{result.procedures.length}개</dd>
          </div>
          <div>
            <dt>법령 근거 연결 수</dt>
            <dd>{legalReferenceCount}개</dd>
          </div>
          <div>
            <dt>{labelFor("area_square_meters")}</dt>
            <dd>{formatArea(result.area_square_meters)}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">절차 로드맵</p>
            <h2>절차 진행 흐름</h2>
            <p className="muted">분석 엔진이 반환한 절차를 순서대로 표시하고, 단계별 필요 정보와 법령 근거를 함께 보여줍니다.</p>
          </div>
          <span className="badge neutral">{result.procedures.length}개 단계</span>
        </div>
        <ProcedureRoadmap steps={result.procedures} />
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

      <details className="developerDetails">
        <summary>개발자용 원문 응답 보기</summary>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </details>
    </section>
  );
}
