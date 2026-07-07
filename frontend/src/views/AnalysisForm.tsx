import { FormEvent, useState } from "react";
import { analyzeProject } from "../api/analyze";
import type { AnalyzeRequest, AnalyzeResponse } from "../api/types";
import { AnalysisResult } from "./AnalysisResult";

const initialForm: AnalyzeRequest = {
  project_name: "TEST_PROJECT_DO_NOT_USE",
  location: "TEST_LOCATION_DO_NOT_USE",
  area_square_meters: 100000,
  implementation_method: "mixed",
  implementer_type: "public_private_spc",
  local_government: "TEST_LOCAL_GOVERNMENT_DO_NOT_USE",
  as_of: ""
};

export function AnalysisForm() {
  const [form, setForm] = useState<AnalyzeRequest>(initialForm);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<K extends keyof AnalyzeRequest>(key: K, value: AnalyzeRequest[K]) {
    setForm((current) => ({ ...current, [key]: value }));
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
      setError(err instanceof Error ? err.message : "Analysis request failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panelHeader">
          <h1>Analysis</h1>
          <span className="badge">POST /api/analyze</span>
        </div>
        <form className="formGrid" onSubmit={submit}>
          <label>
            Project name
            <input value={form.project_name} onChange={(event) => updateField("project_name", event.target.value)} required />
          </label>
          <label>
            Location
            <input value={form.location} onChange={(event) => updateField("location", event.target.value)} required />
          </label>
          <label>
            Area m2
            <input type="number" min="1" value={form.area_square_meters} onChange={(event) => updateField("area_square_meters", Number(event.target.value))} required />
          </label>
          <label>
            Method
            <select value={form.implementation_method} onChange={(event) => updateField("implementation_method", event.target.value)}>
              <option value="mixed">mixed</option>
              <option value="expropriation_or_use">expropriation_or_use</option>
              <option value="replotting">replotting</option>
            </select>
          </label>
          <label>
            Operator type
            <select value={form.implementer_type} onChange={(event) => updateField("implementer_type", event.target.value)}>
              <option value="public_private_spc">public_private_spc</option>
              <option value="public">public</option>
              <option value="private">private</option>
            </select>
          </label>
          <label>
            Local government
            <input value={form.local_government} onChange={(event) => updateField("local_government", event.target.value)} required />
          </label>
          <label>
            as_of
            <input type="date" value={form.as_of ?? ""} onChange={(event) => updateField("as_of", event.target.value)} />
          </label>
          <div className="formActions">
            <button type="submit" disabled={isSubmitting}>{isSubmitting ? "Submitting" : "Analyze"}</button>
          </div>
        </form>
        {error && <p className="error">{error}</p>}
      </section>
      <AnalysisResult result={result} />
    </div>
  );
}
