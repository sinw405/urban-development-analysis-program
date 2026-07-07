import type { AnalyzeResponse, LegalReference, ProcedureStep } from "../api/types";

interface AnalysisResultProps {
  result: AnalyzeResponse | null;
}

function LegalReferences({ references }: { references: LegalReference[] }) {
  if (references.length === 0) {
    return <p className="empty">연결된 법령 근거 없음</p>;
  }

  return (
    <div className="referenceList">
      {references.map((reference, index) => (
        <div className="reference" key={`${reference.step_code}-${reference.article_id ?? index}`}>
          <div className="metaGrid">
            <span>law_id</span><strong>{reference.law_id ?? "-"}</strong>
            <span>article_id</span><strong>{reference.article_id ?? "-"}</strong>
            <span>reference_status</span><strong>{reference.reference_status}</strong>
            <span>placeholder</span><strong>{reference.placeholder}</strong>
          </div>
          {reference.current_version ? (
            <div className="versionBox">
              <span>current version</span>
              <strong>#{reference.current_version.version_id}</strong>
              <span>{reference.current_version.temporal_status}</span>
              <span>{reference.current_version.effective_date ?? "no effective date"}</span>
            </div>
          ) : (
            <p className="empty">current version 없음</p>
          )}
          {reference.versions.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>version_id</th>
                  <th>status</th>
                  <th>effective_date</th>
                  <th>source</th>
                </tr>
              </thead>
              <tbody>
                {reference.versions.map((version) => (
                  <tr key={version.version_id}>
                    <td>{version.version_id}</td>
                    <td>{version.temporal_status}</td>
                    <td>{version.effective_date ?? "-"}</td>
                    <td>{version.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}

function ProcedureCard({ step }: { step: ProcedureStep }) {
  return (
    <article className="card">
      <div className="cardTitle">
        <h3>{step.sequence}. {step.step_name}</h3>
        <code>{step.step_code}</code>
      </div>
      <p>{step.description}</p>
      <div className="metaGrid compact">
        <span>duration</span><strong>{step.estimated_duration}</strong>
        <span>basis</span><strong>{step.legal_basis_placeholder.join(", ")}</strong>
      </div>
      <LegalReferences references={step.legal_references} />
    </article>
  );
}

export function AnalysisResult({ result }: AnalysisResultProps) {
  if (!result) {
    return <p className="empty">분석 결과가 아직 없습니다.</p>;
  }

  return (
    <section className="stack">
      <div className="panel subtle">
        <h2>{result.project_name}</h2>
        <div className="metaGrid">
          <span>analysis_id</span><strong>{result.analysis_id ?? "-"}</strong>
          <span>project_id</span><strong>{result.project_id ?? "-"}</strong>
          <span>as_of</span><strong>{result.as_of ?? "not set"}</strong>
          <span>area</span><strong>{result.area_square_meters.toLocaleString()} m2</strong>
        </div>
      </div>
      <section>
        <h2>Procedure Steps</h2>
        <div className="stack">
          {result.procedures.map((step) => <ProcedureCard key={step.step_code} step={step} />)}
        </div>
      </section>
      <section>
        <h2>Assessment Placeholders</h2>
        <table>
          <thead>
            <tr>
              <th>code</th>
              <th>status</th>
              <th>threshold</th>
              <th>legal_basis</th>
            </tr>
          </thead>
          <tbody>
            {result.assessments.map((item) => (
              <tr key={item.assessment_code ?? item.name}>
                <td>{item.assessment_code ?? "-"}</td>
                <td>{item.status}</td>
                <td>{item.threshold}</td>
                <td>{item.legal_basis}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </section>
  );
}
