// frontend/src/api/client.ts
// Phase 1 — migrated from .js. Types added; logic unchanged.
// Unified axios-based API client wrapper for the frontend.
// Exports:
//  - api (axios instance)
//  - getApiBase()
//  - apiRequest(method, url, {params, data})
//  - setToken/getToken/clearToken
//  - me() - GET /me
//  - login(username, password) - POST /login (x-www-form-urlencoded)

import axios, { AxiosError, CanceledError, type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { buildApiUrl, buildWsUrl, getApiBaseUrl, getApiOrigin } from './runtime';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import type { LoginResult } from '../types/domain/auth';
import { parseLoginResponse, AuthInvariantViolationError } from '../types/auth-mapper';
import type { LoginResponseRaw, UserDto } from '../types/api';
import type { HttpApiError } from '../types/errors';
import { decodeJwtClaims, numericClaim } from '../utils/jwt';

const API_BASE = getApiBaseUrl();
// PR-39 / Medium-11: CSRF bootstrap defaults to ON. Set VITE_CSRF_BOOTSTRAP=0
// to explicitly disable (e.g., for local dev without backend CSRF support).
const CSRF_BOOTSTRAP_ENABLED = import.meta.env.VITE_CSRF_BOOTSTRAP !== '0';
// audit/phase-3, BS-56: opt-in fail-closed mode for CSRF.
// When `VITE_CSRF_STRICT === '1'`, state-changing requests WITHOUT a CSRF
// token are REJECTED locally instead of being sent to the backend.
// Default is fail-open (current behaviour) to avoid breaking deployments
// that don't expose `/auth/csrf-token`. Enable in production once the
// backend is confirmed to serve the endpoint reliably.
const CSRF_STRICT_MODE = import.meta.env.VITE_CSRF_STRICT === '1';
const GLOBAL_RATE_LIMIT_COOLDOWN_MS = 60_000;
// The legacy key mixed route-specific and shared 429s, so it is intentionally ignored.
const GLOBAL_RATE_LIMIT_STORAGE_KEY = 'clinic_api_global_rate_limit_until';
let globalRateLimitUntil = 0;
let globalRateLimitLogAt = 0;
const requestRateLimitUntil = new Map<string, number>();

function getRateLimitRequestKey(config: Pick<AxiosRequestConfig, 'url' | 'baseURL' | 'method'>): string | null {
  if (!config.url) return null;

  try {
    const baseURL = config.baseURL || API_BASE || window.location.origin;
    const requestUrl = new URL(config.url, baseURL);
    return `${requestUrl.origin}:${String(config.method || 'get').toUpperCase()}:${requestUrl.pathname}`;
  } catch {
    const path = config.url.split(/[?#]/, 1)[0];
    return path ? `${String(config.method || 'get').toUpperCase()}:${path}` : null;
  }
}

function isAuthenticationRateLimitedRequest(url?: string): boolean {
  if (!url) return false;

  try {
    const requestUrl = new URL(url, API_BASE || window.location.origin);
    return /\/(?:auth|authentication|2fa)(?:\/|$)/i.test(requestUrl.pathname);
  } catch {
    return /\/(?:auth|authentication|2fa)(?:\/|$)/i.test(url.split(/[?#]/, 1)[0]);
  }
}

function getRetryAfterMs(error: AxiosError): number | null {
  const headers = error.response?.headers;
  const getHeader = (headers as { get?: (name: string) => unknown } | undefined)?.get;
  const retryAfter = getHeader?.call(headers, 'Retry-After')
    ?? headers?.['retry-after']
    ?? headers?.['Retry-After'];
  if (typeof retryAfter !== 'string' && typeof retryAfter !== 'number') return null;

  const value = String(retryAfter).trim();
  const seconds = Number(value);
  if (value && Number.isFinite(seconds)) return Math.max(0, seconds * 1000);

  const retryAt = Date.parse(value);
  return Number.isFinite(retryAt) ? Math.max(0, retryAt - Date.now()) : null;
}

function rememberRequestRateLimit(key: string, until: number): void {
  const now = Date.now();
  for (const [existingKey, existingUntil] of requestRateLimitUntil) {
    if (existingUntil <= now) requestRateLimitUntil.delete(existingKey);
  }

  requestRateLimitUntil.delete(key);
  requestRateLimitUntil.set(key, until);
  while (requestRateLimitUntil.size > 128) {
    const oldestKey = requestRateLimitUntil.keys().next().value;
    if (oldestKey === undefined) break;
    requestRateLimitUntil.delete(oldestKey);
  }
}

function readPersistedRateLimitUntil() {
  try {
    const raw = window.localStorage.getItem(GLOBAL_RATE_LIMIT_STORAGE_KEY);
    const parsed = Number(raw || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  } catch {
    return 0;
  }
}

function persistRateLimitUntil(until: number): void {
  try {
    window.localStorage.setItem(GLOBAL_RATE_LIMIT_STORAGE_KEY, String(until || 0));
  } catch {
    // ignore storage failures
  }
}

globalRateLimitUntil = Math.max(globalRateLimitUntil, readPersistedRateLimitUntil());

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  // Optionally timeout: timeout: 15000,
});

// ✅ SECURITY: Check if token is expiring soon (within 5 minutes)
// AUTH-FE-001 (audit 3886): exported for fail-first tests (jwt.claims.test.ts).
export function isTokenExpiringSoon(token: string | null | undefined): boolean {
  if (!token) return true;
  // AUTH-FE-001 (audit 3886): толерантный Base64URL-декодер. Прежний
  // «сырой» atob бросал InvalidCharacterError на легальных `-`/`_`
  // в JWT payload — catch возвращал false, и проактивный refresh
  // молча skip-ался (оставалась только реактивная 401-страховка).
  // Битый/не-JWT токен по-прежнему false: не триггерим превентивный
  // refresh — 401-реактивный путь остаётся авторитетом.
  const claims = decodeJwtClaims(token);
  if (claims === null) return false;
  const exp = numericClaim(claims, 'exp');
  if (exp === null) return false;
  const expiresAt = exp * 1000;
  const fiveMinutes = 5 * 60 * 1000;
  return Date.now() > (expiresAt - fiveMinutes);
}

function isAccessTokenUnexpired(token: string | null): boolean {
  if (!token) return false;
  const exp = numericClaim(decodeJwtClaims(token), 'exp');
  return exp !== null && exp * 1000 > Date.now();
}

// ✅ SECURITY: Single-flight pattern for token refresh
// Prevents race conditions when multiple requests detect token expiring
interface AuthSessionSnapshot {
  accessToken: string | null;
  refreshToken: string | null;
  generation: number;
}

type SessionBoundRequestConfig = InternalAxiosRequestConfig & {
  _authSessionSnapshot?: AuthSessionSnapshot;
  _retriedAfterRefresh?: boolean;
};

interface TokenRefreshResult {
  accessToken: string | null;
  attemptedAccessToken: string | null;
  attemptedRefreshToken: string | null;
  attemptedSessionGeneration: number;
  resultingRefreshToken: string | null;
  failureStatus?: number;
  sessionChanged: boolean;
}

interface TokenRefreshFlight extends AuthSessionSnapshot {
  promise: Promise<TokenRefreshResult> | null;
}

interface ProactiveRefreshCooldown extends AuthSessionSnapshot {
  retryAfter: number;
}

const PROACTIVE_REFRESH_401_COOLDOWN_MS = 30_000;
let refreshFlight: TokenRefreshFlight | null = null;
let proactiveRefreshCooldown: ProactiveRefreshCooldown | null = null;
let observedCredentials: Omit<AuthSessionSnapshot, 'generation'> | null = null;
let authSessionGeneration = 0;

function getCurrentAuthSession(): AuthSessionSnapshot {
  const credentials = {
    accessToken: tokenManager.getAccessToken(),
    refreshToken: tokenManager.getRefreshToken()
  };
  if (!observedCredentials
    || observedCredentials.accessToken !== credentials.accessToken
    || observedCredentials.refreshToken !== credentials.refreshToken) {
    // Token changes made outside this module indicate a new login/logout.
    // Successful refreshes update observedCredentials explicitly below and
    // keep the same generation.
    observedCredentials = credentials;
    authSessionGeneration += 1;
  }
  return { ...credentials, generation: authSessionGeneration };
}

function sameCredentials(left: AuthSessionSnapshot, right: AuthSessionSnapshot): boolean {
  return left.accessToken === right.accessToken && left.refreshToken === right.refreshToken;
}

function sameAuthSession(left: AuthSessionSnapshot, right: AuthSessionSnapshot): boolean {
  return left.generation === right.generation && sameCredentials(left, right);
}

function isCurrentAuthSession(session: AuthSessionSnapshot): boolean {
  return session.generation === getCurrentAuthSession().generation;
}

function createSessionChangedError(): CanceledError<unknown> {
  return new CanceledError('Request canceled because the authenticated session changed');
}

function createTokenRefreshResult(
  attemptedSession: AuthSessionSnapshot,
  accessToken: string | null,
  options: {
    resultingRefreshToken?: string | null;
    failureStatus?: number;
    sessionChanged?: boolean;
  } = {}
): TokenRefreshResult {
  return {
    accessToken,
    attemptedAccessToken: attemptedSession.accessToken,
    attemptedRefreshToken: attemptedSession.refreshToken,
    attemptedSessionGeneration: attemptedSession.generation,
    resultingRefreshToken: options.resultingRefreshToken ?? null,
    ...(options.failureStatus === undefined ? {} : { failureStatus: options.failureStatus }),
    sessionChanged: options.sessionChanged ?? false
  };
}

/**
 * Refresh only the session pair supplied by the caller. Recheck that pair
 * after the network await before writing rotated credentials.
 */
async function performTokenRefresh(attemptedSession: AuthSessionSnapshot): Promise<TokenRefreshResult> {
  const refreshToken = attemptedSession.refreshToken;
  const result = (
    accessToken: string | null,
    options: Parameters<typeof createTokenRefreshResult>[2] = {}
  ) => createTokenRefreshResult(attemptedSession, accessToken, options);

  if (!isCurrentAuthSession(attemptedSession)) {
    return result(null, { sessionChanged: true });
  }
  if (!refreshToken) return result(null);

  try {
    logger.log('🔄 Refreshing access token...');
    const response = await axios.post(buildApiUrl('/authentication/refresh'), {
      refresh_token: refreshToken
    });

    if (response.data && response.data.access_token) {
      const currentSession = getCurrentAuthSession();
      if (!sameAuthSession(currentSession, attemptedSession)) {
        logger.warn('🔄 Auth session changed during refresh; discarding its result');
        return result(null, { sessionChanged: true });
      }
      proactiveRefreshCooldown = null;
      const newToken = response.data.access_token;
      const newRefreshToken = response.data.refresh_token || refreshToken;
      tokenManager.setAccessToken(newToken);
      // AUTH-REAUDIT-28: backend rotates refresh tokens on each /refresh —
      // persist the new one so future refreshes work.
      if (response.data.refresh_token) {
        tokenManager.setRefreshToken(newRefreshToken);
      }
      // This credential rotation belongs to the same login session; update
      // the observed pair without advancing its generation.
      observedCredentials = { accessToken: newToken, refreshToken: newRefreshToken };
      api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
      logger.log('✅ Token refreshed successfully');

      return result(newToken, { resultingRefreshToken: newRefreshToken });
    }
    const currentSession = getCurrentAuthSession();
    return result(null, { sessionChanged: currentSession.generation !== attemptedSession.generation });
  } catch (err) {
    const status = (err as AxiosError | undefined)?.response?.status;
    const currentSession = getCurrentAuthSession();
    const sessionChanged = currentSession.generation !== attemptedSession.generation;
    if (status === 401 && !sessionChanged) {
      proactiveRefreshCooldown = {
        ...attemptedSession,
        retryAfter: Date.now() + PROACTIVE_REFRESH_401_COOLDOWN_MS
      };
    }
    // Axios errors contain request config and payloads (including refresh
    // credentials). Keep logs limited to the response status.
    logger.warn('❌ Token refresh failed', {
      status: typeof status === 'number' ? status : null
    });
    return result(null, {
      failureStatus: sessionChanged || typeof status !== 'number' ? undefined : status,
      sessionChanged
    });
  }
}

function getOrStartTokenRefresh(session: AuthSessionSnapshot): Promise<TokenRefreshResult> {
  const currentSession = getCurrentAuthSession();
  if (currentSession.generation !== session.generation) {
    return Promise.resolve(createTokenRefreshResult(session, null, { sessionChanged: true }));
  }
  if (refreshFlight && sameAuthSession(refreshFlight, currentSession) && refreshFlight.promise) {
    return refreshFlight.promise;
  }

  const flight: TokenRefreshFlight = { ...currentSession, promise: null };
  const promise = performTokenRefresh(currentSession).finally(() => {
    // An older session's completion must not clear a newer session's flight.
    if (refreshFlight === flight) refreshFlight = null;
  });
  flight.promise = promise;
  refreshFlight = flight;
  return promise;
}

function createRefreshUnauthorizedError(): AxiosError {
  const response: Partial<AxiosResponse> = {
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    data: { detail: 'Not authenticated' },
    config: {} as InternalAxiosRequestConfig
  };
  // Do not retain the failed refresh request config: its body contains the
  // refresh token. Without a business-request config the response interceptor
  // also cannot start a second refresh attempt for this synthetic rejection.
  return new AxiosError(
    'Request failed with status code 401',
    'ERR_BAD_REQUEST',
    undefined,
    undefined,
    response as AxiosResponse
  );
}

/**
 * Refresh token with single-flight pattern.
 * All concurrent callers wait for the same promise, preventing multiple refresh calls.
 * Proactive: only refreshes when the access token is missing or expiring soon.
 * @returns {Promise<string|null>} New access token or null on failure
 */
interface PreparedRequestSession {
  accessToken: string | null;
  session: AuthSessionSnapshot;
}

async function refreshTokenIfNeeded(requestSession: AuthSessionSnapshot): Promise<PreparedRequestSession> {
  let session = getCurrentAuthSession();
  if (session.generation !== requestSession.generation) throw createSessionChangedError();

  const token = session.accessToken;
  const refreshToken = session.refreshToken;

  // No tokens or not expiring - return the credentials captured for this
  // login session. Never substitute credentials from a later session.
  if (!token || !refreshToken || !isTokenExpiringSoon(token)) {
    return { accessToken: token, session };
  }

  // An access token remains usable until its own exp claim. Keep a valid
  // near-expiry session alive for the warning/explicit-extension flow and
  // avoid retrying a rejected refresh on every page request. Cooldown belongs
  // to the exact credential pair, so a new login is never held by old backoff.
  if (proactiveRefreshCooldown
    && sameAuthSession(proactiveRefreshCooldown, session)
    && proactiveRefreshCooldown.retryAfter > Date.now()
    && isAccessTokenUnexpired(token)) {
    return { accessToken: token, session };
  }

  if (refreshFlight && sameAuthSession(refreshFlight, session) && refreshFlight.promise) {
    logger.log('🔄 Refresh already in progress, waiting...');
  }

  const result = await getOrStartTokenRefresh(session);
  session = getCurrentAuthSession();
  if (session.generation !== requestSession.generation || result.sessionChanged) {
    throw createSessionChangedError();
  }

  if (result.accessToken) {
    const expectedRefreshedSession: AuthSessionSnapshot = {
      accessToken: result.accessToken,
      refreshToken: result.resultingRefreshToken,
      generation: result.attemptedSessionGeneration
    };
    if (!sameAuthSession(session, expectedRefreshedSession)) throw createSessionChangedError();
    return { accessToken: result.accessToken, session };
  }

  if (result.failureStatus === 401) {
    const isAttemptedCredentialsStillCurrent = sameAuthSession(session, {
      accessToken: result.attemptedAccessToken,
      refreshToken: result.attemptedRefreshToken,
      generation: result.attemptedSessionGeneration
    });

    if (isAttemptedCredentialsStillCurrent) {
      if (isAccessTokenUnexpired(session.accessToken)) {
        return { accessToken: session.accessToken, session };
      }
      logger.warn('🔒 Refresh token rejected — ending the matching session');
      invalidateDeadSession();
      throw createRefreshUnauthorizedError();
    }
    // Another login replaced the credentials while this refresh was pending.
    // Cancel the old business request; do not replay it as the new principal.
    throw createSessionChangedError();
  }

  // A network or 5xx failure is transient. Continue only while the same
  // access token is still valid; do not send a known-expired credential.
  if (!isAccessTokenUnexpired(session.accessToken)) {
    throw createRefreshUnauthorizedError();
  }
  return { accessToken: session.accessToken, session };
}

/**
 * Reactive single-flight refresh (401 recovery): refresh regardless of the
 * local expiry heuristic. Shares the same mutex as refreshTokenIfNeeded so
 * a burst of 401s triggers exactly one /authentication/refresh call.
 */
async function forceRefreshTokenWithResult(session: AuthSessionSnapshot): Promise<TokenRefreshResult> {
  if (refreshFlight !== null && sameAuthSession(refreshFlight, session)) {
    logger.log('🔄 Reactive refresh already in progress, waiting...');
  }
  return getOrStartTokenRefresh(session);
}

async function forceRefreshToken(): Promise<string | null> {
  // An explicit operator retry should bypass the automatic 401 backoff.
  const session = getCurrentAuthSession();
  proactiveRefreshCooldown = null;
  const refreshResult = await forceRefreshTokenWithResult(session);
  return refreshResult.accessToken;
}

// Endpoints that bootstrap or replace the session themselves — a 401/403
// from these must never trigger the reactive refresh/retry path.
const AUTH_BOOTSTRAP_SUFFIXES = [
  '/auth/login',
  '/authentication/login',
  '/auth/refresh',
  '/authentication/refresh',
  '/auth/csrf-token',
  '/auth/password-reset',
  '/authentication/password-reset',
  '/password-reset',
  '/password-reset/confirm',
  '/auth/logout',
  '/authentication/logout',
  // Patient portal (Phase 0 PR-A1/A2): pre-session endpoints whose uniform
  // anti-enum 400/401/429 must surface as form errors — they must never
  // trigger the reactive refresh/retry path (a patient session has no
  // refresh_token, and a 401 here means "wrong code / not activated",
  // not "token expired").
  '/patient-access/request-otp',
  '/patient-access/verify-otp',
  '/patient-access/login',
  '/patient-access/activate/request-otp',
  '/patient-access/activate/confirm'
];

function isAuthBootstrapEndpoint(url: string | undefined): boolean {
  const path = String(url || '').split(/[?#]/, 1)[0];
  return AUTH_BOOTSTRAP_SUFFIXES.some((suffix) => path.endsWith(suffix));
}

function isPendingTwoFactorChallenge(url: string | undefined, data: unknown): boolean {
  const path = String(url || '').split(/[?#]/, 1)[0];
  if (!path.endsWith('/2fa/verify')) return false;

  let body = data;
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body) as unknown;
    } catch {
      return false;
    }
  }
  if (body === null || typeof body !== 'object' || Array.isArray(body)) return false;
  const pendingToken = (body as Record<string, unknown>).pending_2fa_token;
  return typeof pendingToken === 'string' && pendingToken.trim().length > 0;
}

// ✅ SECURITY: Get CSRF token from cookie
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() ?? null;
  return null;
}

// ✅ SECURITY: Fetch CSRF token from server if not in cookie
let csrfTokenPromise: Promise<string | null> | null = null;
let csrfEndpointUnavailable = false;
let csrfBootstrapSkippedLogged = false;
async function ensureCSRFToken(): Promise<string | null> {
  // Check cookie first
  const cookieToken = getCookie('csrf_token');
  if (cookieToken) return cookieToken;
  if (!CSRF_BOOTSTRAP_ENABLED) {
    if (!csrfBootstrapSkippedLogged) {
      logger.info('[FIX:CSRF] CSRF bootstrap endpoint disabled; using cookie-only mode');
      csrfBootstrapSkippedLogged = true;
    }
    return null;
  }
  if (csrfEndpointUnavailable) return null;

  // Single-flight pattern for CSRF token fetch
  if (csrfTokenPromise) return csrfTokenPromise;

  csrfTokenPromise = (async () => {
    try {
      const response = await axios.get(`${API_BASE}/auth/csrf-token`, {
        withCredentials: true
      });
      return response.data?.csrf_token || getCookie('csrf_token');
    } catch (err) {
      const axiosErr = err as HttpApiError;
      if (axiosErr?.response?.status === 404) {
        csrfEndpointUnavailable = true;
        logger.info('[FIX:CSRF] Backend does not expose /auth/csrf-token; skipping CSRF header bootstrap');
        return null;
      }
      logger.warn('Failed to get CSRF token:', err);
      return null;
    } finally {
      csrfTokenPromise = null;
    }
  })();

  return csrfTokenPromise;
}

// Ensure Authorization header is attached for every request from localStorage
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const boundConfig = config as SessionBoundRequestConfig;
  const now = Date.now();
  const requestUrl = String(config.url || '');
  const shouldBindSession = !isAuthBootstrapEndpoint(requestUrl)
    && !isPendingTwoFactorChallenge(requestUrl, config.data);
  let requestSession = boundConfig._authSessionSnapshot;
  if (!requestSession) {
    requestSession = getCurrentAuthSession();
    boundConfig._authSessionSnapshot = requestSession;
  } else if (shouldBindSession && !isCurrentAuthSession(requestSession)) {
    return Promise.reject(createSessionChangedError());
  }

  const rateLimitKey = getRateLimitRequestKey(config);
  const requestCooldownUntil = rateLimitKey ? requestRateLimitUntil.get(rateLimitKey) || 0 : 0;
  if (now < requestCooldownUntil) {
    logger.warn('[FIX:429] Request-specific cooldown active', {
      cooldownUntil: new Date(requestCooldownUntil).toISOString(),
      method: String(config.method || 'get').toUpperCase()
    });
    return Promise.reject(createLocalRateLimitError(config, requestCooldownUntil - now, 'request'));
  }

  if (now < globalRateLimitUntil && !isAuthenticationRateLimitedRequest(requestUrl)) {
    if (now - globalRateLimitLogAt > 10_000) {
      logger.warn('[API] Global 429 cooldown active', {
        cooldownUntil: new Date(globalRateLimitUntil).toISOString()
      });
      globalRateLimitLogAt = now;
    }
    persistRateLimitUntil(globalRateLimitUntil);
    return Promise.reject(createLocalRateLimitError(config, globalRateLimitUntil - now, 'global'));
  }

  // Don't preemptively refresh on authentication bootstrap or the pending
  // 2FA challenge. A challenge uses its own one-time token, not this session.
  let token: string | null;
  if (shouldBindSession) {
    const prepared = await refreshTokenIfNeeded(requestSession);
    requestSession = prepared.session;
    boundConfig._authSessionSnapshot = requestSession;
    token = prepared.accessToken;
  } else {
    // Auth bootstrap and pending 2FA keep their existing request semantics.
    token = tokenManager.getAccessToken();
  }

  if (shouldBindSession && !isCurrentAuthSession(requestSession)) {
    return Promise.reject(createSessionChangedError());
  }
  // PR-39 / Medium-12: Removed tokenPreview logging — was leaking first 20 chars
  // of the JWT to the browser console (visible in production via devtools).
  // Now we only log whether a token exists (boolean), not its content.
  if (import.meta.env.MODE === 'development') {
    logger.log('[api/client.js] Request:', { url: config.url, hasToken: !!token });
  }
  if (token) {
    const t = typeof token === 'string' ? token.trim() : token;
    if (t) {
      config.headers.set('Authorization', `Bearer ${t}`);
    }
  }

  // ✅ CSRF: Add X-CSRF-Token for state-changing requests
  const method = config.method?.toLowerCase() ?? '';
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = await ensureCSRFToken();
    if (csrfToken) {
      config.headers.set('X-CSRF-Token', csrfToken);
    } else if (CSRF_STRICT_MODE) {
      // audit/phase-3, BS-56: fail-closed path. Without this branch, a
      // misconfigured backend (no `/auth/csrf-token`, cookie miss, transient
      // network error) silently allowed every state-changing request to
      // proceed without CSRF protection for the entire session — the
      // `csrfEndpointUnavailable` flag is sticky. In strict mode we reject
      // the request locally so the operator sees a clear failure instead of
      // a silent security gap. The auth endpoints (login/refresh) are
      // exempt because they bootstrap the CSRF token itself.
      const url = config.url || '';
      const isAuthEndpoint = url.endsWith('/auth/login')
        || url.endsWith('/auth/refresh')
        || url.endsWith('/authentication/refresh')
        || url.endsWith('/auth/csrf-token')
        || url.endsWith('/auth/logout');
      if (!isAuthEndpoint) {
        return Promise.reject(new Error(
          `[FIX:CSRF] Strict mode: refusing ${method.toUpperCase()} ${url} without CSRF token. `
          + 'Set VITE_CSRF_STRICT=0 to revert to fail-open behaviour.'
        ));
      }
    }
  }

  if (shouldBindSession) {
    const currentSession = getCurrentAuthSession();
    if (currentSession.generation !== requestSession.generation) {
      return Promise.reject(createSessionChangedError());
    }
    // A successful refresh in another request may have rotated credentials
    // while CSRF was loading. Rebind within the same login session to the
    // latest pair before dispatching.
    requestSession = currentSession;
    boundConfig._authSessionSnapshot = currentSession;
    if (currentSession.accessToken) {
      config.headers.set('Authorization', `Bearer ${currentSession.accessToken}`);
    }
  }

  return config;
});

// ✅ SECURITY: Handle 401 responses - log but don't auto-clear tokens
// (prevents race condition where 401 during login transition clears new token)

// Phase 0 follow-up (owner P2, access-only session lifecycle): the 401
// recovery path must be able to TERMINATE a dead access-only session
// (Patient portal login/activation install sessions with no refresh
// token) through the same machinery as an explicit logout - clearing
// auth_token/auth_profile + tokenManager + PHI caches and notifying
// subscribers so RouteAccessBoundary redirects immediately instead of
// showing a zombie session. The auth store registers the hook below
// (stores/auth.ts imports this module, so the listener keeps the import
// direction acyclic); when no store is loaded (standalone client tests)
// the fallback still drops the client-level credentials.
export type SessionInvalidationListener = () => void;
let sessionInvalidationListener: SessionInvalidationListener | null = null;

export function setSessionInvalidationListener(listener: SessionInvalidationListener | null): void {
  sessionInvalidationListener = listener;
}

function invalidateDeadSession(): void {
  proactiveRefreshCooldown = null;
  const listener = sessionInvalidationListener;
  if (listener) {
    try {
      listener();
    } catch (e) {
      logger.warn('[api] session invalidation listener failed:', e);
    }
  }
  // Belt-and-suspenders: even without the store hook, drop client-level
  // credentials so guards and the request interceptor see an anonymous
  // state (idempotent with the listener path).
  tokenManager.clearAll();
  getCurrentAuthSession();
  delete api.defaults.headers.common['Authorization'];
}

// #05 Tier 1: Detect CSRF rejection from the backend.
// The backend sets `X-CSRF-Status: rejected` header and returns
// { "detail": "CSRF validation failed", "reason": "missing_cookie|missing_header|mismatch" }
// when CSRF validation fails. This is distinct from a regular 403
// (permission denied) and should trigger automatic token refresh + retry,
// NOT logout.
function isCSRFRejection(error: AxiosError): boolean {
  if (error.response?.status !== 403) return false;
  const headers = error.response?.headers;
  if (headers) {
    const csrfStatus = headers['x-csrf-status'] || headers['X-CSRF-Status'];
    if (csrfStatus === 'rejected') return true;
  }
  const data = error.response?.data as Record<string, unknown> | undefined;
  if (data && typeof data === 'object') {
    const reason = data.reason;
    if (typeof reason === 'string' && ['missing_cookie', 'missing_header', 'mismatch'].includes(reason)) {
      return true;
    }
  }
  return false;
}

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    // Reactive 401 recovery: one single-flight refresh + retry for requests
    // that went out WITH an Authorization header. Auth bootstrap endpoints
    // are exempt; anonymous requests stay untouched (route guards decide).
    // On refresh failure the session is cleared ONLY when the failed token
    // is still the current one — clearing blindly would wipe a freshly
    // logged-in session during the login transition (see NOTE below).
    if (
      error.response?.status === 401 &&
      error.config &&
      !isAuthBootstrapEndpoint(error.config.url) &&
      !isPendingTwoFactorChallenge(error.config.url, error.config.data)
    ) {
      const config = error.config as SessionBoundRequestConfig;
      const hadAuthHeader = !!config.headers?.Authorization;
      const failedToken = String(config.headers?.Authorization || '')
        .replace(/^Bearer\s+/i, '');
      const liveSession = getCurrentAuthSession();
      const requestSession = config._authSessionSnapshot ?? {
        accessToken: failedToken || liveSession.accessToken,
        refreshToken: liveSession.refreshToken,
        generation: liveSession.generation
      };
      const requestStillBelongsToCurrentSession = requestSession.generation === liveSession.generation;
      const refreshToken = liveSession.refreshToken;

      if (hadAuthHeader && !requestStillBelongsToCurrentSession) {
        return Promise.reject(createSessionChangedError());
      }

      if (hadAuthHeader && requestStillBelongsToCurrentSession && refreshToken && !config._retriedAfterRefresh) {
        config._retriedAfterRefresh = true;
        logger.warn('🔒 401 received — single-flight refresh + retry', {
          url: config.url
        });
        const refreshResult = await forceRefreshTokenWithResult(liveSession);
        const afterRefreshSession = getCurrentAuthSession();
        if (refreshResult.sessionChanged || afterRefreshSession.generation !== requestSession.generation) {
          // A login/logout won the race. Never replay the old operation using
          // credentials installed by the replacement session.
          return Promise.reject(createSessionChangedError());
        }
        if (refreshResult.accessToken) {
          const refreshedSession: AuthSessionSnapshot = {
            accessToken: refreshResult.accessToken,
            refreshToken: refreshResult.resultingRefreshToken,
            generation: refreshResult.attemptedSessionGeneration
          };
          if (!sameAuthSession(afterRefreshSession, refreshedSession)) {
            return Promise.reject(error);
          }
          config._authSessionSnapshot = afterRefreshSession;
          config.headers.set('Authorization', `Bearer ${refreshResult.accessToken}`);
          return api.request(config);
        }
        const failedRefreshSessionIsStillCurrent = refreshResult.failureStatus === 401
          && afterRefreshSession.generation === refreshResult.attemptedSessionGeneration
          && afterRefreshSession.accessToken === refreshResult.attemptedAccessToken
          && afterRefreshSession.refreshToken === refreshResult.attemptedRefreshToken;
        if (failedRefreshSessionIsStillCurrent) {
          // N2-5 review round 3 (P1): a STAFF session whose refresh died is
          // terminated through the SAME machinery as the access-only path
          // below — invalidateDeadSession() (the auth-store listener:
          // auth_token/auth_profile + PHI caches + subscriber notify, so
          // RouteAccessBoundary redirects at once) plus the idempotent
          // client-level credential drop. The old manual clearAll() left
          // auth_profile and the React auth subscribers untouched: the
          // staff UI (e.g. the Nurse tablet) kept rendering a zombie
          // logged-in session with no guaranteed redirect.
          logger.warn('🔒 Token refresh failed — clearing dead session');
          invalidateDeadSession();
        }
      } else if (hadAuthHeader && requestStillBelongsToCurrentSession && !refreshToken) {
        // Access-only session (Patient portal): no refresh token exists, so
        // the reactive refresh branch above never runs. Phase 0 follow-up
        // (owner P2): without this branch a dead 30-minute JWT used to leave
        // the session installed — every request kept 401ing while the UI
        // still showed the patient as logged in. Clear the session, keeping
        // the SAME race guard as the refresh path: the decision is made on
        // the LIVE access token re-read at rejection time. If a newer login
        // replaced the principal mid-flight, liveToken differs from
        // failedToken and the replacement survives untouched.
        const liveToken = liveSession.accessToken;
        if (liveToken && failedToken === liveToken) {
          logger.warn('🔒 401 on access-only session (no refresh token) — clearing dead session', {
            url: config.url
          });
          invalidateDeadSession();
        }
      }
    }
    if (error.response?.status === 401) {
      logger.warn('🔒 Unauthorized response received', {
        url: error.config?.url,
        hadToken: !!error.config?.headers?.Authorization
      });
      // NOTE: Token clearing removed to prevent race condition during login.
      // User will be redirected to login by RoleGuard or route protection instead.
    }
    if (error.response?.status === 429 && (error as AxiosError & { clientRateLimit?: boolean }).clientRateLimit !== true) {
      const failedConfig = error.config || error.response.config;
      const requestKey = getRateLimitRequestKey(failedConfig);
      const retryAfterMs = getRetryAfterMs(error);
      const requestScoped = retryAfterMs !== null || isAuthenticationRateLimitedRequest(failedConfig?.url);

      if (requestScoped && requestKey) {
        const cooldownMs = retryAfterMs ?? GLOBAL_RATE_LIMIT_COOLDOWN_MS;
        const cooldownUntil = Date.now() + cooldownMs;
        rememberRequestRateLimit(requestKey, cooldownUntil);
        logger.warn('[FIX:429] HTTP 429 received, limiting cooldown to the request', {
          method: String(failedConfig.method || 'get').toUpperCase(),
          cooldownMs
        });
      } else {
        globalRateLimitUntil = Date.now() + GLOBAL_RATE_LIMIT_COOLDOWN_MS;
        globalRateLimitLogAt = 0;
        persistRateLimitUntil(globalRateLimitUntil);
        logger.warn('[FIX:429] HTTP 429 received, enabling shared API cooldown', {
          cooldownMs: GLOBAL_RATE_LIMIT_COOLDOWN_MS
        });
      }
    }

    // #05 Tier 1: CSRF 403 recovery — refresh token and retry exactly once.
    // This handles CSRF cookie drift (8h expiry, multi-tab, subdomain mixup).
    // The backend provides "recovery": "GET /auth/csrf-token" hint.
    if (isCSRFRejection(error) && error.config) {
      const config = error.config as InternalAxiosRequestConfig & { _csrfRetried?: boolean };
      if (!config._csrfRetried) {
        config._csrfRetried = true;
        logger.info('[FIX:CSRF] CSRF rejection detected — refreshing token and retrying once', {
          url: config.url,
        });
        // Reset cached state so ensureCSRFToken() will re-fetch.
        csrfEndpointUnavailable = false;
        csrfTokenPromise = null;
        const newToken = await ensureCSRFToken();
        if (newToken) {
          config.headers.set('X-CSRF-Token', newToken);
          return api.request(config);
        }
        logger.warn('[FIX:CSRF] Could not obtain new CSRF token — rejecting request');
      } else {
        logger.warn('[FIX:CSRF] CSRF retry already attempted — not retrying again', {
          url: config.url,
        });
      }
    }

    return Promise.reject(error);
  }
);

function getApiBase(): string {
  return API_BASE;
}

function setToken(token: string | null | undefined): void {
  if (token) {
    const t = typeof token === 'string' ? token.trim() : token;
    if (t) {
      tokenManager.setAccessToken(t);
      api.defaults.headers.common['Authorization'] = `Bearer ${t}`;
    }
  } else {
    tokenManager.clearAll();
    delete api.defaults.headers.common['Authorization'];
  }
}

function getToken(): string | null {
  return tokenManager.getAccessToken();
}

function clearToken(): void {
  setToken(null);
}

/**
 * Persist refresh token after login or after successful /authentication/refresh.
 * Uses tokenManager so the storage key stays consistent.
 */
function setRefreshToken(token: string | null | undefined): void {
  if (token) {
    const t = typeof token === 'string' ? token.trim() : token;
    if (t) {
      tokenManager.setRefreshToken(t);
      return;
    }
  }
  tokenManager.setRefreshToken(null);
}

function getRefreshToken(): string | null {
  return tokenManager.getRefreshToken();
}

interface LocalRateLimitError {
  name: string;
  message: string;
  config: InternalAxiosRequestConfig;
  isAxiosError: boolean;
  clientRateLimit: true;
  response: {
    status: number;
    statusText: string;
    data: unknown;
    config: InternalAxiosRequestConfig;
  };
}

function createLocalRateLimitError(
  config: InternalAxiosRequestConfig,
  cooldownMs: number,
  scope: 'global' | 'request',
): LocalRateLimitError {
  const error = new Error('Client-side cooldown active after HTTP 429') as unknown as LocalRateLimitError;
  error.name = 'AxiosError';
  error.config = config;
  error.isAxiosError = true;
  error.clientRateLimit = true;
  error.response = {
    status: 429,
    statusText: 'Too Many Requests',
    data: {
      detail: scope === 'global'
        ? 'Превышен общий лимит запросов. Клиент временно приостановил API-запросы после 429.'
        : 'Превышен лимит запросов к этому адресу. Клиент временно приостановил повтор.',
      cooldownMs,
      scope
    },
    config
  };
  return error;
}

/**
 * Generic request wrapper that normalizes server error detail.
 * Usage: await apiRequest('get', '/visits/visits', { params: { limit: 10 } })
 *
 * Optional zod schema validation: pass a `schema` in the options to
 * validate the response data at runtime. Invalid responses throw.
 *
 * Usage with schema:
 *   import { z } from 'zod';
 *   const PatientSchema = z.object({ id: z.number(), name: z.string() });
 *   const patient = await apiRequest('get', '/patients/1', { schema: PatientSchema });
 */
async function apiRequest<T = unknown>(
  method: string,
  url: string,
  { params = {}, data = {}, schema }: { params?: Record<string, unknown>; data?: unknown; schema?: import('zod').ZodType<T> } = {},
): Promise<T> {
  try {
    const resp = await api.request({ method, url, params, data });
    if (schema) {
      const result = schema.safeParse(resp.data);
      if (!result.success) {
        logger.warn('[API] Response validation failed', { url, method, errors: result.error.issues });
        throw new Error(`Response validation failed for ${method.toUpperCase()} ${url}`);
      }
      return result.data;
    }
    return resp.data as T;
  } catch (err) {
    // Normalize error payloads so callers can handle them uniformly.
    const axiosErr = err as HttpApiError;
    if (axiosErr?.response?.data) {
      const d = axiosErr.response.data;
      // common FastAPI shapes: { "detail": "msg" } or { "detail": [ ... ] }
      if (d && d.detail) {
        throw d.detail;
      }
      // fallback: throw entire response data
      throw d;
    }
    // network or unknown error
    throw err;
  }
}

/**
 * Convenience API helpers used by frontend code
 */
async function me(): Promise<UserDto> {
  // GET /auth/me
  const resp = await api.get<UserDto>('/auth/me');
  return resp.data;
}

/**
 * login: perform OAuth2 password flow (x-www-form-urlencoded).
 *
 * Returns the domain LoginResult (discriminated union). Callers should narrow
 * with `if (result.requires_2fa) { ... } else { ... }`.
 *
 * The raw DTO from the backend is validated by parseLoginResponse(), which
 * enforces AUTHENTICATION_LAWS_FOR_AI.md ЗАКОН 2 (blocking 2FA flow):
 *   - requires_2fa === true  ⇒  no access_token in response
 *   - requires_2fa === false ⇒  access_token + refresh_token present,
 *                                no pending_2fa_token
 *
 * If the backend violates ЗАКОН 2, parseLoginResponse throws
 * AuthInvariantViolationError. The stable invariant identifier is logged
 * here without the response DTO or error message, then the error is re-thrown.
 *
 * Caller should call setToken(result.access_token) to persist tokens
 * (only valid in the `requires_2fa === false` branch).
 */
async function login(username: string, password: string): Promise<LoginResult> {
  const credentials = {
    username,
    password,
    remember_me: false,
  };

  const resp = await api.post('/authentication/login', credentials);
  const dto = resp.data as LoginResponseRaw;

  try {
    return parseLoginResponse(dto);
  } catch (err) {
    if (err instanceof AuthInvariantViolationError) {
      // The DTO may contain access or pending-2FA credentials. Log only the
      // stable invariant identifier so logger sanitization is not the boundary.
      logger.error('[api/client] login() backend violated auth invariant:', err.invariant);
    }
    throw err;
  }
}

// Backwards-compatible alias expected by live consumers (10+ files import `apiClient`).
// Other legacy aliases (setAuthToken, setAxiosAuthToken, setBearerToken, getProfile, get)
// were removed 2026-07-25 — zero importers across the codebase.
const apiClient = api;

// Инициализируем токен при загрузке модуля
const existingToken = tokenManager.getAccessToken();
if (existingToken) {
  api.defaults.headers.common['Authorization'] = `Bearer ${existingToken}`;
}

export {
  api,
  apiClient,
  getApiOrigin,
  getApiBase,
  getApiBaseUrl,
  buildApiUrl,
  buildWsUrl,
  apiRequest,
  setToken,
  getToken,
  setRefreshToken,
  getRefreshToken,
  clearToken,
  me,
  login,
  ensureCSRFToken,
  isCSRFRejection,
  // PR 3351 (review round 9, P2): канонический single-flight refresh для
  // UI-контролов продления сессии (кнопка «Продлить сессию» в LabPanel).
  // Тот же мьютекс, что и у 401-recovery: клик по кнопке не порождает
  // параллельный /authentication/refresh поверх уже идущего.
  forceRefreshToken,
};

export default apiClient;
