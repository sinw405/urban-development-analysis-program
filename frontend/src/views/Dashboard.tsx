import { apiBaseUrl } from "../api/client";
import type { Route } from "../router";

interface DashboardProps {
  onNavigate: (route: Route) => void;
}

export function Dashboard({ onNavigate }: DashboardProps) {
  return (
    <section className="panel">
      <div className="panelHeader">
        <h1>Urban Development Analysis</h1>
        <span className="badge">MVP</span>
      </div>
      <p className="muted">Backend API base URL: <code>{apiBaseUrl}</code></p>
      <div className="grid two">
        <button className="tileButton" onClick={() => onNavigate("/analyze")}>
          <strong>Run Analysis</strong>
          <span>Submit project inputs to <code>/api/analyze</code>.</span>
        </button>
        <button className="tileButton" onClick={() => onNavigate("/law-updates")}>
          <strong>Law Update Events</strong>
          <span>Review stored events from <code>/api/law-updates</code>.</span>
        </button>
      </div>
    </section>
  );
}
