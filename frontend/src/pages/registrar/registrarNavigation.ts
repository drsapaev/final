/**
 * Registrar Panel — navigation helpers for Backend-driven UI.
 *
 * Strategic Direction 3 (audit §8): migrate from URL query params
 * (?view=welcome, ?view=queue) to proper nested routes (/registrar/welcome,
 * /registrar/queue) while maintaining backward compatibility.
 *
 * Phase 1 (this PR): add route registry entries for /registrar/welcome
 * and /registrar/queue. These are siblings of /registrar, not nested
 * children, because the current routeRegistry architecture doesn't
 * support nested children. Each sibling route reuses the RegistrarPanel
 * component with an initial view state derived from the path.
 *
 * Phase 2 (future): migrate RegistrarPanel to use React Router's
 * useLocation() to read the current path and derive currentView from
 * it, deprecating ?view= query param entirely.
 *
 * Backward compatibility:
 * - ?view=welcome still works (handled by currentView useMemo in RegistrarPanel)
 * - ?view=queue still works
 * - /registrar/welcome is a new canonical path
 * - /registrar/queue is a new canonical path
 */

/**
 * Map of view names to canonical paths.
 * Used by navigation helpers and route registry.
 */
export const REGISTRAR_VIEW_PATHS = {
  welcome: '/registrar/welcome',
  queue: '/registrar/queue',
  worklist: '/registrar',
};

/**
 * Map of paths back to view names.
 */
export const REGISTRAR_PATH_TO_VIEW = {
  '/registrar/welcome': 'welcome',
  '/registrar/queue': 'queue',
  // PR-51: /registrar now maps to 'welcome' (was null=worklist).
  // The welcome dashboard is the registrar's landing page — showing the
  // worklist table on first login was confusing (no overview, no quick actions).
  // Worklist is still accessible via the header "Все записи" button or
  // by navigating to /registrar/worklist.
  '/registrar': 'welcome',
};

/**
 * Returns the canonical path for a registrar view.
 *
 * @param {string|null} view - 'welcome', 'queue', or null/undefined for worklist
 * @param {Object} [searchParams] - optional URLSearchParams to preserve
 * @returns {string} canonical path with query string preserved
 *
 * @example
 * getRegistrarPath('welcome')  // → '/registrar/welcome'
 * getRegistrarPath('queue', searchParams)  // → '/registrar/queue?date=2026-07-02'
 * getRegistrarPath(null)  // → '/registrar'
 */
export const getRegistrarPath = (view, searchParams) => {
  const basePath = REGISTRAR_VIEW_PATHS[view] || REGISTRAR_VIEW_PATHS.worklist;
  if (!searchParams) return basePath;

  // Clone searchParams and remove the legacy ?view= param (canonical path replaces it)
  const params = new URLSearchParams(searchParams);
  params.delete('view');
  params.delete('tab');

  const queryString = params.toString();
  return queryString ? `${basePath}?${queryString}` : basePath;
};

/**
 * Returns the view name derived from the current pathname.
 * Returns null for the default worklist view.
 *
 * @param {string} pathname - from useLocation().pathname
 * @returns {string|null} 'welcome', 'queue', or null
 *
 * @example
 * getViewFromPath('/registrar/welcome')  // → 'welcome'
 * getViewFromPath('/registrar/queue')    // → 'queue'
 * getViewFromPath('/registrar')          // → null (worklist)
 * getViewFromPath('/registrar/anything') // → null
 */
export const getViewFromPath = (pathname) => {
  return REGISTRAR_PATH_TO_VIEW[pathname] ?? null;
};

/**
 * Returns true if the given pathname is a registrar route
 * (either the main panel or a sub-view).
 *
 * @param {string} pathname
 * @returns {boolean}
 */
export const isRegistrarRoute = (pathname) => {
  return pathname === '/registrar' ||
         pathname.startsWith('/registrar/');
};

/**
 * Navigation helper for switching between registrar views.
 * Returns an object suitable for use with react-router's navigate()
 * or Link `to` prop.
 *
 * @param {string|null} view - target view ('welcome', 'queue', null for worklist)
 * @param {Object} [searchParams] - current URLSearchParams to preserve
 * @returns {{ pathname: string, search: string }}
 */
export const navigateToRegistrarView = (view, searchParams) => {
  const pathname = REGISTRAR_VIEW_PATHS[view] || REGISTRAR_VIEW_PATHS.worklist;
  if (!searchParams) return { pathname, search: '' };

  const params = new URLSearchParams(searchParams);
  params.delete('view');
  params.delete('tab');

  return {
    pathname,
    search: params.toString() ? `?${params.toString()}` : '',
  };
};

export default {
  REGISTRAR_VIEW_PATHS,
  REGISTRAR_PATH_TO_VIEW,
  getRegistrarPath,
  getViewFromPath,
  isRegistrarRoute,
  navigateToRegistrarView,
};
