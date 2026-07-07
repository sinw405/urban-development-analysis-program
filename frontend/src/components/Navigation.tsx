import type { Route } from "../router";

interface NavigationProps {
  currentRoute: Route;
  onNavigate: (route: Route) => void;
}

const items: Array<{ route: Route; label: string }> = [
  { route: "/", label: "대시보드" },
  { route: "/analyze", label: "사업 분석" },
  { route: "/law-updates", label: "법령 개정 감지" }
];

export function Navigation({ currentRoute, onNavigate }: NavigationProps) {
  return (
    <nav className="nav" aria-label="주요 화면">
      {items.map((item) => (
        <button
          key={item.route}
          className={currentRoute === item.route ? "active" : ""}
          onClick={() => onNavigate(item.route)}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
