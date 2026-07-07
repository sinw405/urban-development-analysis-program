export type Route = "/" | "/analyze" | "/analyses" | "/law-updates" | `/analyses/${string}`;

export function getRouteFromLocation(): Route {
  const pathname = window.location.pathname;
  if (pathname === "/analyze" || pathname === "/analyses" || pathname === "/law-updates") {
    return pathname;
  }
  if (pathname.startsWith("/analyses/")) {
    return pathname as Route;
  }
  return "/";
}

export function getAnalysisIdFromRoute(route: Route): number | null {
  if (!route.startsWith("/analyses/")) {
    return null;
  }
  const rawId = route.replace("/analyses/", "");
  const parsed = Number(rawId);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}
