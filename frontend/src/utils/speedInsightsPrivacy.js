const SENSITIVE_ROUTE_SEGMENT = '[redacted]';
const UUID_SEGMENT_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const isDynamicRouteMatch = (routePath, pathname) => {
  const routeParts = routePath.split('/').filter(Boolean);
  const pathParts = pathname.split('/').filter(Boolean);

  if (routeParts.length !== pathParts.length) {
    return false;
  }

  return routeParts.every((part, index) => part.startsWith(':') || part === pathParts[index]);
};

const redactUnmatchedPath = (pathname) => {
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

export function sanitizeSpeedInsightsEvent(event, routes) {
  if (!event || typeof event !== 'object' || typeof event.url !== 'string') {
    return event;
  }

  try {
    const parsed = new URL(event.url, 'https://clinic.local');
    const matchedRoute = (routes || []).find((route) => isDynamicRouteMatch(route.path, parsed.pathname));
    const safeUrl = matchedRoute?.path || redactUnmatchedPath(parsed.pathname);

    return {
      ...event,
      url: safeUrl,
      route: matchedRoute?.path || event.route,
    };
  } catch {
    return {
      ...event,
      url: SENSITIVE_ROUTE_SEGMENT,
    };
  }
}
