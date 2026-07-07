import { useEffect, useState } from "react";
import { Navigation } from "./components/Navigation";
import { Dashboard } from "./views/Dashboard";
import { AnalysisForm } from "./views/AnalysisForm";
import { LawUpdates } from "./views/LawUpdates";
import { getRouteFromLocation, Route } from "./router";

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

  return (
    <div className="appShell">
      <header className="topbar">
        <div>
          <strong>Urban Development Analysis</strong>
          <span>Phase 8 Frontend MVP</span>
        </div>
        <Navigation currentRoute={route} onNavigate={navigate} />
      </header>
      <main>
        {route === "/" && <Dashboard onNavigate={navigate} />}
        {route === "/analyze" && <AnalysisForm />}
        {route === "/law-updates" && <LawUpdates />}
      </main>
    </div>
  );
}
