import { useEffect, useState } from "react";
import { getAnalysisDetail, listAnalyses, summarizeAnalysis } from "../api/analyses";
import { apiBaseUrl } from "../api/client";
import type { AnalysisHistoryRow } from "../api/types";
import type { Route } from "../router";
import { formatDate } from "../utils/formatters";

interface DashboardProps {
  onNavigate: (route: Route) => void;
}

export function Dashboard({ onNavigate }: DashboardProps) {
  const [recentAnalyses, setRecentAnalyses] = useState<AnalysisHistoryRow[]>([]);
  const [isLoadingRecent, setIsLoadingRecent] = useState(true);
  const [recentError, setRecentError] = useState<string | null>(null);

  useEffect(() => {
    async function loadRecentAnalyses() {
      setIsLoadingRecent(true);
      setRecentError(null);
      try {
        const data = await listAnalyses({ limit: 5, offset: 0, sort: "created_at_desc" });
        const rows = await Promise.all(
          data.items.map(async (item) => summarizeAnalysis(item, await getAnalysisDetail(item.analysis_id)))
        );
        setRecentAnalyses(rows);
      } catch (err) {
        setRecentError(err instanceof Error ? err.message : "최근 분석 이력을 불러오지 못했습니다.");
      } finally {
        setIsLoadingRecent(false);
      }
    }

    void loadRecentAnalyses();
  }, []);

  return (
    <section className="stack">
      <div className="pageTitle">
        <div>
          <p className="eyebrow">대시보드</p>
          <h1>로컬 데모 검증 화면</h1>
          <p className="lead">
            사업 분석 요청, 분석 이력 조회, 절차별 법령 근거 표시, 법령 개정 감지 내역을 한 화면 흐름으로 확인합니다.
          </p>
        </div>
        <span className="badge neutral">TEST 데이터 기반</span>
      </div>

      <div className="noticeBox">
        현재는 개발 검증용 TEST 데이터 기반 MVP 단계입니다. 실제 법령 조문, 조문번호, 기준값은 후속 단계에서 법제처 연동과 검토를 거쳐 반영됩니다.
      </div>

      <div className="dashboardGrid">
        <article className="actionCard">
          <span className="cardKicker">사업 분석</span>
          <h2>사업 분석 시작</h2>
          <p>사업 정보를 입력하면 예상 인허가 절차와 연결된 법령 근거 메타데이터를 확인할 수 있습니다.</p>
          <button type="button" onClick={() => onNavigate("/analyze")}>사업 분석 화면으로 이동</button>
        </article>

        <article className="actionCard">
          <span className="cardKicker">분석 이력</span>
          <h2>저장된 분석 결과 확인</h2>
          <p>과거에 저장된 분석 결과를 목록으로 확인하고 상세 화면에서 다시 열어봅니다.</p>
          <button type="button" onClick={() => onNavigate("/analyses")}>전체 분석 이력 보기</button>
        </article>

        <article className="actionCard">
          <span className="cardKicker">개정 감지</span>
          <h2>법령 개정 감지 내역</h2>
          <p>감지된 TEST 법령 개정 이벤트와 영향받는 절차 코드를 확인합니다.</p>
          <button type="button" onClick={() => onNavigate("/law-updates")}>개정 감지 내역 보기</button>
        </article>

        <article className="infoCard">
          <span className="cardKicker">현재 상태</span>
          <h2>개발 검증 상태</h2>
          <ul className="checkList">
            <li>백엔드 API 응답을 화면에서 확인하는 단계입니다.</li>
            <li>법제처 실제 네트워크 호출은 비활성화되어 있습니다.</li>
            <li>RAG와 실제 법령 데이터 구축은 아직 포함되지 않았습니다.</li>
          </ul>
        </article>
      </div>

      <section className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">최근 분석 이력</p>
            <h2>최근 저장된 분석</h2>
            <p className="muted">최근 5건의 분석 결과를 빠르게 확인합니다.</p>
          </div>
          <button type="button" onClick={() => onNavigate("/analyses")}>전체 분석 이력 보기</button>
        </div>

        {isLoadingRecent ? <div className="loadingBox">최근 분석 이력을 불러오는 중입니다.</div> : null}
        {recentError && (
          <div className="errorBox">
            <strong>최근 분석 이력을 불러오지 못했습니다.</strong>
            <p>대시보드의 다른 기능은 계속 사용할 수 있습니다.</p>
            <details>
              <summary>개발자용 오류 상세</summary>
              <pre>{recentError}</pre>
            </details>
          </div>
        )}
        {!isLoadingRecent && !recentError && recentAnalyses.length === 0 ? (
          <p className="emptyState">저장된 분석 이력이 없습니다.</p>
        ) : null}
        {recentAnalyses.length > 0 && (
          <div className="recentList">
            {recentAnalyses.map((analysis) => (
              <button
                type="button"
                className="recentItem"
                key={analysis.analysis_id}
                onClick={() => onNavigate(`/analyses/${analysis.analysis_id}`)}
              >
                <strong>#{analysis.analysis_id} {analysis.project_name}</strong>
                <span>기준일 {formatDate(analysis.as_of)} · 절차 {analysis.procedure_count}개 · 법령 근거 {analysis.legal_reference_count}개</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <article className="infoCard">
        <span className="cardKicker">로컬 실행</span>
        <h2>로컬 테스트 안내</h2>
        <p>백엔드 실행, 마이그레이션 적용, demo seed 실행 후 프론트엔드를 실행하세요.</p>
        <div className="commandList">
          <code>docker compose exec backend python -m app.dev_seed</code>
          <code>npm run dev</code>
        </div>
      </article>

      <div className="metaPanel">
        <span>백엔드 API 주소</span>
        <code>{apiBaseUrl}</code>
      </div>
    </section>
  );
}
