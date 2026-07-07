export type Route = "/" | "/analyze" | "/law-updates";

export function getRouteFromLocation(): Route {
  const pathname = window.location.pathname;
  if (pathname === "/analyze" || pathname === "/law-updates") {
    return pathname;
  }
  return "/";
}
