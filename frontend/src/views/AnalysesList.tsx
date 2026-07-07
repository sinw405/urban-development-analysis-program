import { useEffect, useState } from "react";
import { getAnalysisDetail, listAnalyses, summarizeAnalysis } from "../api/analyses";
import type { AnalysisHistoryRow } from "../api/types";
import type { Route } from "../router";
import { formatDate } from "../utils/formatters";

interface AnalysesListProps {
  onNavigate: (route: Route) => void;
}

export function AnalysesList({ onNavigate }: AnalysesListProps) {
  const [rows, setRows] = useState<AnalysisHistoryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listAnalyses({ limit: 20, offset: 0, sort: "created_at_desc" });
      const enriched = await Promise.all(
        data.items.map(async (item) => summarizeAnalysis(item, await getAnalysisDetail(item.analysis_id)))
      );
      setRows(enriched);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "분석 이력을 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">분석 이력</p>
          <h1>저장된 분석 이력</h1>
          <p className="muted">저장된 분석 결과를 목록으로 확인하고 상세 화면에서 다시 열어봅니다.</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={isLoading}>새로고침</button>
      </div>

      {error && (
        <div className="errorBox">
          <strong>분석 이력을 불러오지 못했습니다.</strong>
          <p>백엔드 서버가 실행 중인지 확인해 주세요.</p>
          <details>
            <summary>개발자용 오류 상세</summary>
            <pre>{error}</pre>
          </details>
        </div>
      )}

      {isLoading ? <div className="loadingBox">분석 이력을 불러오는 중입니다.</div> : null}
      {!isLoading && !error && rows.length === 0 ? <p className="emptyState">저장된 분석 이력이 없습니다.</p> : null}

      {rows.length > 0 && (
        <>
          <p className="muted">총 {total.toLocaleString("ko-KR")}건 중 최근 {rows.length.toLocaleString("ko-KR")}건을 표시합니다.</p>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>분석 ID</th>
                  <th>사업명</th>
                  <th>프로젝트 ID</th>
                  <th>기준일</th>
                  <th>생성일</th>
                  <th>절차 수</th>
                  <th>법령 근거 연결 수</th>
                  <th>상세 보기</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.analysis_id}>
                    <td>{row.analysis_id}</td>
                    <td>{row.project_name}</td>
                    <td>{row.project_id}</td>
                    <td>{formatDate(row.as_of)}</td>
                    <td>{formatDate(row.created_at)}</td>
                    <td>{row.procedure_count}개</td>
                    <td>{row.legal_reference_count}개</td>
                    <td>
                      <button className="smallButton" type="button" onClick={() => onNavigate(`/analyses/${row.analysis_id}`)}>
                        상세 보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="developerDetails compactDetails">
            <summary>개발자용 목록 원문 보기</summary>
            <pre>{JSON.stringify(rows, null, 2)}</pre>
          </details>
        </>
      )}
    </section>
  );
}

