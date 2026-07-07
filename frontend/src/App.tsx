import { useEffect, useState } from "react";
import { Navigation } from "./components/Navigation";
import { Dashboard } from "./views/Dashboard";
import { AnalysisForm } from "./views/AnalysisForm";
import { AnalysisDetailView } from "./views/AnalysisDetailView";
import { AnalysesList } from "./views/AnalysesList";
import { LawUpdates } from "./views/LawUpdates";
import { getAnalysisIdFromRoute, getRouteFromLocation, Route } from "./router";

export function App() {
  const [route, setRoute] = useState<Route>(getRouteFromLocation());

  function navigate(nextRoute: Route) {
    window.history.pushState(null, "", nextRoute);
    setRoute(nextRoute);
  }

  useEffect(() => {
    function handlePopState() {
      setRoute(getRouteFromLocation());
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const analysisId = getAnalysisIdFromRoute(route);

  return (
    <div className="appShell">
      <header className="topbar">
        <div className="brandBlock">
          <strong>도시개발사업 절차 분석 프로그램</strong>
          <span>개발 검증용 MVP 화면</span>
        </div>
        <Navigation currentRoute={route} onNavigate={navigate} />
      </header>
      <main>
        {route === "/" && <Dashboard onNavigate={navigate} />}
        {route === "/analyze" && <AnalysisForm />}
        {route === "/analyses" && <AnalysesList onNavigate={navigate} />}
        {analysisId !== null && <AnalysisDetailView analysisId={analysisId} onNavigate={navigate} />}
        {route === "/law-updates" && <LawUpdates />}
      </main>
      <footer className="appFooter">
        현재 화면은 개발 검증용 MVP입니다. 실제 법령 조문과 기준값은 아직 연동되지 않았으며, TEST_*_DO_NOT_USE 데이터는 화면 검증용 데이터입니다.
      </footer>
    </div>
  );
}
