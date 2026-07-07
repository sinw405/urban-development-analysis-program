import { useEffect, useState } from "react";
import { analysisDetailToResult, getAnalysisDetail } from "../api/analyses";
import type { AnalysisDetail } from "../api/types";
import type { Route } from "../router";
import { AnalysisResult } from "./AnalysisResult";

interface AnalysisDetailViewProps {
  analysisId: number;
  onNavigate: (route: Route) => void;
}

export function AnalysisDetailView({ analysisId, onNavigate }: AnalysisDetailViewProps) {
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        setDetail(await getAnalysisDetail(analysisId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "분석 상세 정보를 불러오지 못했습니다.");
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [analysisId]);

  return (
    <section className="stack">
      <div className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">분석 상세</p>
            <h1>분석 상세 #{analysisId}</h1>
            <p className="muted">저장된 분석 결과를 다시 열어 절차와 법령 근거를 확인합니다.</p>
          </div>
          <button type="button" onClick={() => onNavigate("/analyses")}>목록으로 돌아가기</button>
        </div>

        {isLoading ? <div className="loadingBox">분석 상세 정보를 불러오는 중입니다.</div> : null}
        {error && (
          <div className="errorBox">
            <strong>분석 상세 정보를 불러오지 못했습니다.</strong>
            <p>분석 ID가 존재하는지 또는 백엔드 서버가 실행 중인지 확인해 주세요.</p>
            <details>
              <summary>개발자용 오류 상세</summary>
              <pre>{error}</pre>
            </details>
          </div>
        )}
      </div>

      {detail && <AnalysisResult result={analysisDetailToResult(detail)} />}

      {detail && (
        <details className="developerDetails">
          <summary>개발자용 저장 상세 원문 보기</summary>
          <pre>{JSON.stringify(detail, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}
