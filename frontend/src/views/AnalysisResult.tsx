import type { AnalyzeResponse, LegalReference, ProcedureStep } from "../api/types";
import { countLegalReferences, formatArea, formatDate, formatStatus } from "../utils/formatters";
import { labelFor } from "../utils/labels";

interface AnalysisResultProps {
  result: AnalyzeResponse | null;
}

function StatusBadge({ value }: { value: string | null | undefined }) {
  return <span className={`statusBadge status-${value ?? "unknown"}`}>{formatStatus(value)}</span>;
}

function LegalReferenceTable({ references }: { references: LegalReference[] }) {
  if (references.length === 0) {
    return <p className="emptyState">연결된 법령 근거 없음</p>;
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

            {reference.versions.length > 0 && (
              <div className="tableWrap nestedTable">
                <table>
                  <thead>
                    <tr>
                      <th>{labelFor("version_id")}</th>
                      <th>{labelFor("version_status")}</th>
                      <th>{labelFor("effective_date")}</th>
                      <th>{labelFor("source")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reference.versions.map((version) => (
                      <tr key={version.version_id}>
                        <td>{version.version_id}</td>
                        <td><StatusBadge value={version.temporal_status ?? version.version_status} /></td>
                        <td>{formatDate(version.effective_date)}</td>
                        <td>{version.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

function ProcedureSummaryTable({ steps }: { steps: ProcedureStep[] }) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>단계 코드</th>
            <th>단계명</th>
            <th>설명</th>
            <th>법령 근거 연결 여부</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((step) => (
            <tr key={step.step_code}>
              <td><code>{step.step_code}</code></td>
              <td>{step.step_name}</td>
              <td>{step.description}</td>
              <td>{step.legal_references.length > 0 ? `${step.legal_references.length}개 연결` : "연결된 법령 근거 없음"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProcedureLegalReferences({ step }: { step: ProcedureStep }) {
  return (
    <article className="card resultCard">
      <div className="cardTitle">
        <div>
          <h3>{step.sequence}. {step.step_name}</h3>
          <p className="muted"><code>{step.step_code}</code></p>
        </div>
        <span className="badge">법령 근거 {step.legal_references.length}개</span>
      </div>
      <p>{step.description}</p>
      <dl className="definitionGrid compactDefinition">
        <dt>{labelFor("estimated_duration")}</dt>
        <dd>{step.estimated_duration}</dd>
        <dt>조문 확인 상태</dt>
        <dd>{step.legal_basis_placeholder.join(", ")}</dd>
      </dl>
      <LegalReferenceTable references={step.legal_references} />
    </article>
  );
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
            <h2>절차 목록</h2>
            <p className="muted">분석 엔진이 반환한 절차와 법령 근거 연결 여부입니다.</p>
          </div>
        </div>
        <ProcedureSummaryTable steps={result.procedures} />
      </section>

      <section className="stack">
        <div className="sectionHeading">
          <h2>단계별 법령 근거</h2>
          <p className="muted">백엔드가 반환한 ID, 키, 상태, 시행일, 출처만 표시합니다.</p>
        </div>
        {result.procedures.map((step) => <ProcedureLegalReferences key={step.step_code} step={step} />)}
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
