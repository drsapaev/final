/**
 * Единая SPA-navigation policy.
 *
 * UX Audit (cross-cutting issue 10.4) выявил 3 способа навигации:
 *   - SPA `navigate()` (Landing → Login)
 *   - `window.location.assign('/login')` (Setup после успеха — полная перезагрузка)
 *   - `window.location.href = '/login'` (mcpClient при 401)
 *
 * Этот модуль предоставляет единый API для не-React контекста
 * (axios interceptors, мидлвары, error boundaries).
 *
 * Для React-компонентов используйте `useNavigateSafely` из
 * `utils/navigationReact.js` (он импортирует react-router-dom).
 *
 * `window.location.assign()` допустим ТОЛЬКО для:
 *   - смены auth-домена (например, SSO redirect)
 *   - принудительного hard-reload (например, после смены локали)
 *   - fallback, когда React-роутер недоступен (api/client.js interceptor)
 */

/**
 * Получить текущий pathname безопасно (SSR-friendly).
 * @returns {string}
 */
export function getCurrentPathname() {
  if (typeof window === 'undefined') return '/';
  return window.location.pathname;
}

/**
 * Проверить, находимся ли мы уже на указанном маршруте.
 * Защита от лишних редиректов.
 * @param {string} path
 * @returns {boolean}
 */
export function isOnPath(path) {
  return getCurrentPathname() === path;
}

/**
 * Hard-redirect на /login — ТОЛЬКО для использования в не-React контексте
 * (axios interceptors, мидлвары, error boundaries без router).
 *
 * В React-компонентах нужно использовать useNavigateSafely() из navigationReact.js.
 *
 * @param {object} [options]
 * @param {string} [options.reason] - для логирования, почему выбран hard redirect
 * @param {string} [options.redirectAfter] - URL для возврата после логина (?from=...)
 */
export function hardRedirectToLogin(options: Record<string, unknown> = {}) {
  const { reason = 'unauthorized', redirectAfter } = options;
  if (typeof window === 'undefined') return;
  if (getCurrentPathname() === '/login') return;

   
  console.warn(`[navigation] hard redirect to /login (reason: ${reason})`);

  const target = new URL('/login', window.location.origin);
  if (redirectAfter && redirectAfter !== '/login') {
    target.searchParams.set('from', String(redirectAfter));
  }
  // assign() вместо href= сохраняет историю
  window.location.assign(target.toString());
}

/**
 * Hard-redirect на произвольный маршрут — только когда React Router недоступен
 * (например, при инициализации до mount приложения).
 *
 * @param {string} path
 * @param {object} [options]
 * @param {string} [options.reason]
 */
export function hardRedirectTo(path, options: Record<string, unknown> = {}) {
  const { reason = 'init' } = options;
  if (typeof window === 'undefined') return;
  if (isOnPath(path)) return;
   
  console.warn(`[navigation] hard redirect to ${path} (reason: ${reason})`);
  window.location.assign(path);
}

/**
 * Проверить, является ли URL внешним (другой домен).
 * @param {string} url
 * @returns {boolean}
 */
export function isExternalUrl(url) {
  if (!url || typeof url !== 'string') return false;
  if (url.startsWith('/') || url.startsWith('#')) return false;
  try {
    const parsed = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
    if (typeof window === 'undefined') return true;
    return parsed.origin !== window.location.origin;
  } catch {
    return false;
  }
}

const navigationExports = {
  getCurrentPathname,
  isOnPath,
  hardRedirectToLogin,
  hardRedirectTo,
  isExternalUrl,
};

export default navigationExports;
