import type { Route } from "../router";

interface NavigationProps {
  currentRoute: Route;
  onNavigate: (route: Route) => void;
}

const items: Array<{ route: Route; label: string }> = [
  { route: "/", label: "대시보드" },
  { route: "/analyze", label: "사업 분석" },
  { route: "/analyses", label: "분석 이력" },
  { route: "/law-updates", label: "법령 개정 감지" }
];

function isActive(currentRoute: Route, itemRoute: Route): boolean {
  if (itemRoute === "/analyses") {
    return currentRoute === "/analyses" || currentRoute.startsWith("/analyses/");
  }
  return currentRoute === itemRoute;
}

export function Navigation({ currentRoute, onNavigate }: NavigationProps) {
  return (
    <nav className="nav" aria-label="주요 화면">
      {items.map((item) => (
        <button
          key={item.route}
          className={isActive(currentRoute, item.route) ? "active" : ""}
          onClick={() => onNavigate(item.route)}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
