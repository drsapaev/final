const SENSITIVE_ROUTE_SEGMENT = '[redacted]';
const UUID_SEGMENT_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ABSOLUTE_URL_PATTERN = /^[a-z][a-z0-9+.-]*:\/\/[^/]*(\/.*)?$/i;

const getPathnameFromUrl = (url: string): string | null => {
  const normalized = url.trim();
  if (!normalized) return null;

  const pathWithoutQuery = normalized.split('#')[0].split('?')[0];
  if (pathWithoutQuery.startsWith('/')) {
    return pathWithoutQuery || '/';
  }

  const absoluteMatch = pathWithoutQuery.match(ABSOLUTE_URL_PATTERN);
  if (absoluteMatch) {
    return absoluteMatch[1] || '/';
  }

  return null;
};

const isDynamicRouteMatch = (routePath: string, pathname: string): boolean => {
  const routeParts = routePath.split('/').filter(Boolean);
  const pathParts = pathname.split('/').filter(Boolean);

  if (routeParts.length !== pathParts.length) {
    return false;
  }

  return routeParts.every((part: string, index: number) => part.startsWith(':') || part === pathParts[index]);
};

const redactUnmatchedPath = (pathname: string) => {
  const redacted = pathname
    .split('/')
    .map((part) => {
      if (!part) return part;
      if (/^\d+$/.test(part)) return SENSITIVE_ROUTE_SEGMENT;
      if (UUID_SEGMENT_PATTERN.test(part)) return SENSITIVE_ROUTE_SEGMENT;
      if (/^[A-Za-z0-9_-]{12,}$/.test(part)) return SENSITIVE_ROUTE_SEGMENT;
      return part;
    })
    .join('/');

  return redacted || '/';
};

interface RouteEntry {
  path?: string;
}

interface SpeedInsightsEvent {
  url?: unknown;
  route?: unknown;
  [key: string]: unknown;
}

export function sanitizeSpeedInsightsEvent(
  event: SpeedInsightsEvent,
  routes: ReadonlyArray<RouteEntry>
): SpeedInsightsEvent {
  if (!event || typeof event !== 'object' || typeof event.url !== 'string') {
    return event;
  }

  const pathname = getPathnameFromUrl(event.url);

  if (!pathname) {
    return {
      ...event,
      url: SENSITIVE_ROUTE_SEGMENT,
    };
  }

  const routeList: ReadonlyArray<RouteEntry> = Array.isArray(routes) ? routes : [];
  const matchedRoute = routeList.find(
    (route: RouteEntry) => typeof route?.path === 'string' && isDynamicRouteMatch(route.path as string, pathname)
  );
  const safeUrl: string = matchedRoute?.path || redactUnmatchedPath(pathname);

  return {
    ...event,
    url: safeUrl,
    route: matchedRoute?.path || event.route,
  };
}
