import { FormEvent, useState } from "react";
import { analyzeProject } from "../api/analyze";
import type { AnalyzeRequest, AnalyzeResponse } from "../api/types";
import { methodLabel, operatorLabel } from "../utils/labels";
import { AnalysisResult } from "./AnalysisResult";
import { MunicipalityOrdinanceNotice } from "../components/MunicipalityOrdinanceNotice";

const initialForm: AnalyzeRequest = {
  project_name: "TEST_PROJECT_DO_NOT_USE",
  location: "TEST_LOCATION_DO_NOT_USE",
  area_square_meters: 100000,
  implementation_method: "mixed",
  implementer_type: "public_private_spc",
  local_government: "TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
  as_of: "2099-06-15"
};

export function AnalysisForm() {
  const [form, setForm] = useState<AnalyzeRequest>(initialForm);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<K extends keyof AnalyzeRequest>(key: K, value: AnalyzeRequest[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function resetForm() {
    setForm(initialForm);
    setResult(null);
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const payload: AnalyzeRequest = {
        ...form,
        area_square_meters: Number(form.area_square_meters)
      };
      if (!payload.as_of) {
        delete payload.as_of;
      }
      const data = await analyzeProject(payload);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "분석 요청 실패");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">사업 분석</p>
            <h1>사업 정보 입력</h1>
            <p className="muted">TEST 값을 기준으로 절차와 연결된 법령 근거 메타데이터를 확인합니다.</p>
          </div>
          <span className="badge">POST /api/analyze</span>
        </div>

        <div className="noticeBox compactNotice">
          실제 사업명처럼 보이는 샘플은 사용하지 않습니다. 기본값은 화면 검증 전용 TEST 데이터입니다.
        </div>

        <MunicipalityOrdinanceNotice municipality={form.local_government} variant="input" />

        <form className="formGrid" onSubmit={submit}>
          <label>
            <span>사업명</span>
            <input value={form.project_name} onChange={(event) => updateField("project_name", event.target.value)} required />
            <small>테스트할 사업명을 입력하세요.</small>
          </label>
          <label>
            <span>위치</span>
            <input value={form.location} onChange={(event) => updateField("location", event.target.value)} required />
            <small>테스트용 위치를 입력하세요.</small>
          </label>
          <label>
            <span>사업면적</span>
            <input type="number" min="1" value={form.area_square_meters} onChange={(event) => updateField("area_square_meters", Number(event.target.value))} required />
            <small>숫자만 입력하세요. 단위는 ㎡입니다.</small>
          </label>
          <label>
            <span>시행방식</span>
            <select value={form.implementation_method} onChange={(event) => updateField("implementation_method", event.target.value)}>
              <option value="mixed">{methodLabel("mixed")}</option>
              <option value="expropriation_or_use">{methodLabel("expropriation_or_use")}</option>
              <option value="replotting">{methodLabel("replotting")}</option>
            </select>
            <small>사업 시행방식을 선택하세요.</small>
          </label>
          <label>
            <span>시행자 유형</span>
            <select value={form.implementer_type} onChange={(event) => updateField("implementer_type", event.target.value)}>
              <option value="public_private_spc">{operatorLabel("public_private_spc")}</option>
              <option value="public">{operatorLabel("public")}</option>
              <option value="private">{operatorLabel("private")}</option>
            </select>
            <small>시행자 유형을 선택하세요.</small>
          </label>
          <label>
            <span>관할 지자체</span>
            <input value={form.local_government} onChange={(event) => updateField("local_government", event.target.value)} required />
            <small>테스트용 관할 지자체 값을 입력하세요.</small>
          </label>
          <label>
            <span>기준일</span>
            <input type="date" value={form.as_of ?? ""} onChange={(event) => updateField("as_of", event.target.value)} />
            <small>특정 기준일의 조문 버전을 확인할 때 사용합니다.</small>
          </label>
          <div className="formActions">
            <button type="submit" disabled={isSubmitting}>{isSubmitting ? "분석 요청을 처리하고 있습니다." : "분석 실행"}</button>
            <button type="button" className="secondaryButton" onClick={resetForm} disabled={isSubmitting}>입력값 초기화</button>
          </div>
        </form>

        {error && (
          <div className="errorBox">
            <strong>분석 요청 중 오류가 발생했습니다.</strong>
            <p>백엔드 서버가 실행 중인지 확인해 주세요.</p>
            <details>
              <summary>개발자용 오류 상세</summary>
              <pre>{error}</pre>
            </details>
          </div>
        )}
      </section>

      {isSubmitting && <div className="loadingBox">분석 요청을 처리하고 있습니다.</div>}
      <AnalysisResult result={result} />
    </div>
  );
}
