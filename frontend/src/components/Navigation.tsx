import type { Route } from "../router";

interface NavigationProps {
  currentRoute: Route;
  onNavigate: (route: Route) => void;
}

export function Navigation({ currentRoute, onNavigate }: NavigationProps) {
  return (
    <nav className="nav" aria-label="Primary">
      <button className={currentRoute === "/" ? "active" : ""} onClick={() => onNavigate("/")}>Dashboard</button>
      <button className={currentRoute === "/analyze" ? "active" : ""} onClick={() => onNavigate("/analyze")}>Analysis</button>
      <button className={currentRoute === "/law-updates" ? "active" : ""} onClick={() => onNavigate("/law-updates")}>Law Updates</button>
    </nav>
  );
}
