import { apiBaseUrl } from "../api/client";
import type { Route } from "../router";

interface DashboardProps {
  onNavigate: (route: Route) => void;
}

export function Dashboard({ onNavigate }: DashboardProps) {
  return (
    <section className="stack">
      <div className="pageTitle">
        <div>
          <p className="eyebrow">대시보드</p>
          <h1>로컬 데모 검증 화면</h1>
          <p className="lead">
            사업 분석 요청, 절차별 법령 근거 표시, 법령 개정 감지 내역을 한 화면 흐름으로 확인합니다.
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

        <article className="infoCard">
          <span className="cardKicker">로컬 실행</span>
          <h2>로컬 테스트 안내</h2>
          <p>백엔드 실행, 마이그레이션 적용, demo seed 실행 후 프론트엔드를 실행하세요.</p>
          <div className="commandList">
            <code>docker compose exec backend python -m app.dev_seed</code>
            <code>npm run dev</code>
          </div>
        </article>
      </div>

      <div className="metaPanel">
        <span>백엔드 API 주소</span>
        <code>{apiBaseUrl}</code>
      </div>
    </section>
  );
}
