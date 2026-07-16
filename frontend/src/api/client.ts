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

import axios, { type AxiosError, type AxiosInstance, type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { buildApiUrl, buildWsUrl, getApiBaseUrl, getApiOrigin } from './runtime';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import type { LoginResponse, LoginResult } from '../types/auth';
import { parseLoginResponse, AuthInvariantViolationError } from '../types/auth-mapper';
import type { LoginResponseRaw, User } from '../types/api';

const API_BASE = getApiBaseUrl();
// PR-39 / Medium-11: CSRF bootstrap defaults to ON. Set VITE_CSRF_BOOTSTRAP=0
// to explicitly disable (e.g., for local dev without backend CSRF support).
const CSRF_BOOTSTRAP_ENABLED = import.meta.env.VITE_CSRF_BOOTSTRAP !== '0';
const GLOBAL_RATE_LIMIT_COOLDOWN_MS = 60_000;
let globalRateLimitUntil = 0;
let globalRateLimitLogAt = 0;

function readPersistedRateLimitUntil() {
  try {
    const raw = window.localStorage.getItem('clinic_api_rate_limit_until');
    const parsed = Number(raw || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  } catch {
    return 0;
  }
}

function persistRateLimitUntil(until: number): void {
  try {
    window.localStorage.setItem('clinic_api_rate_limit_until', String(until || 0));
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
function isTokenExpiringSoon(token: string | null | undefined): boolean {
  if (!token) return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return false;
    const payload: { exp?: number } = JSON.parse(atob(parts[1])) as { exp?: number };
    if (!payload.exp) return false;
    const expiresAt = payload.exp * 1000;
    const fiveMinutes = 5 * 60 * 1000;
    return Date.now() > (expiresAt - fiveMinutes);
  } catch {
    return false;
  }
}

// ✅ SECURITY: Single-flight pattern for token refresh
// Prevents race conditions when multiple requests detect token expiring
let refreshPromise: Promise<string | null> | null = null;
let pendingRequestsQueue: Array<(value: string | null) => void> = [];

/**
 * Refresh token with single-flight pattern.
 * All concurrent callers wait for the same promise, preventing multiple refresh calls.
 * @returns {Promise<string|null>} New access token or null on failure
 */
async function refreshTokenIfNeeded(): Promise<string | null> {
  const token = tokenManager.getAccessToken();
  const refreshToken = tokenManager.getRefreshToken();

  // No tokens or not expiring - return immediately
  if (!token || !refreshToken || !isTokenExpiringSoon(token)) {
    return token;
  }

  // ✅ MUTEX: If refresh is already in progress, wait for it
  if (refreshPromise !== null) {
    logger.log('🔄 Refresh already in progress, waiting...');
    return refreshPromise;
  }

  // ✅ Start single refresh operation
  refreshPromise = (async () => {
    try {
      logger.log('🔄 Token expiring soon, refreshing...');
      const response = await axios.post(buildApiUrl('/authentication/refresh'), {
        refresh_token: refreshToken
      });

      if (response.data && response.data.access_token) {
        const newToken = response.data.access_token;
        tokenManager.setAccessToken(newToken);
        api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
        // AUTH-REAUDIT-28: backend rotates refresh tokens on each /refresh —
        // persist the new one so future refreshes work.
        if (response.data.refresh_token) {
          tokenManager.setRefreshToken(response.data.refresh_token);
        }
        logger.log('✅ Token refreshed successfully');

        // Notify all pending requests
        pendingRequestsQueue.forEach(resolve => resolve(newToken));
        pendingRequestsQueue = [];

        return newToken;
      }
      return null;
    } catch (err) {
      logger.warn('❌ Token refresh failed:', err);
      // Notify pending requests of failure
      pendingRequestsQueue.forEach(resolve => resolve(null));
      pendingRequestsQueue = [];
      return null;
    } finally {
      // ✅ Reset mutex after completion
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// ✅ SECURITY: Get CSRF token from cookie
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
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
      if (err?.response?.status === 404) {
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
  const now = Date.now();
  const requestUrl = String(config.url || '');
  if (now < globalRateLimitUntil && !requestUrl.includes('/auth/')) {
    if (now - globalRateLimitLogAt > 10_000) {
      logger.warn('[API] Global 429 cooldown active', {
        cooldownUntil: new Date(globalRateLimitUntil).toISOString(),
        url: requestUrl
      });
      globalRateLimitLogAt = now;
    }
    persistRateLimitUntil(globalRateLimitUntil);
    return Promise.reject(createLocalRateLimitError(config));
  }

  // Try to refresh token if expiring soon (except for auth endpoints)
  if (!config.url?.includes('/auth/')) {
    await refreshTokenIfNeeded();
  }

  const token = tokenManager.getAccessToken();
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
  const method = config.method?.toLowerCase();
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = await ensureCSRFToken();
    if (csrfToken) {
      config.headers.set('X-CSRF-Token', csrfToken);
    }
  }

  return config;
});

// ✅ SECURITY: Handle 401 responses - log but don't auto-clear tokens
// (prevents race condition where 401 during login transition clears new token)
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      logger.warn('🔒 Unauthorized response received', {
        url: error.config?.url,
        hadToken: !!error.config?.headers?.Authorization
      });
      // NOTE: Token clearing removed to prevent race condition during login.
      // User will be redirected to login by RoleGuard or route protection instead.
    }
    if (error.response?.status === 429) {
      globalRateLimitUntil = Date.now() + GLOBAL_RATE_LIMIT_COOLDOWN_MS;
      globalRateLimitLogAt = 0;
      persistRateLimitUntil(globalRateLimitUntil);
      logger.warn('[API] HTTP 429 received, enabling global cooldown', {
        url: error.config?.url,
        cooldownMs: GLOBAL_RATE_LIMIT_COOLDOWN_MS
      });
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
  response: {
    status: number;
    statusText: string;
    data: unknown;
    config: InternalAxiosRequestConfig;
  };
}

function createLocalRateLimitError(config: InternalAxiosRequestConfig): LocalRateLimitError {
  const error = new Error('Client-side cooldown active after HTTP 429') as unknown as LocalRateLimitError;
  error.name = 'AxiosError';
  error.config = config;
  error.isAxiosError = true;
  error.response = {
    status: 429,
    statusText: 'Too Many Requests',
    data: {
      detail: 'Превышен лимит запросов. Клиент временно поставил запросы на паузу после 429.',
      cooldownMs: GLOBAL_RATE_LIMIT_COOLDOWN_MS
    },
    config
  };
  return error;
}

/**
 * Generic request wrapper that normalizes server error detail.
 * Usage: await apiRequest('get', '/visits/visits', { params: { limit: 10 } })
 */
async function apiRequest<T = unknown>(
  method: string,
  url: string,
  { params = {}, data = {} }: { params?: Record<string, unknown>; data?: unknown } = {},
): Promise<T> {
  try {
    const resp = await api.request({ method, url, params, data });
    return resp.data as T;
  } catch (err) {
    // Normalize error payloads so callers can handle them uniformly.
    if (err && err.response && err.response.data) {
      const d = err.response.data;
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
async function me(): Promise<User> {
  // GET /auth/me
  const resp = await api.get<User>('/auth/me');
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
 * AuthInvariantViolationError. The error is logged here and re-thrown so
 * callers can surface it to the user (and the team can surface it to the
 * backend owner).
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
      // Log the invariant violation loudly — backend bugs must be visible.
      logger.error('[api/client] login() backend violated auth invariant:', err.invariant, err.message, err.dto);
    }
    throw err;
  }
}

// Backwards-compatible aliases expected by older frontend code
const setAuthToken = setToken; // alias
const setAxiosAuthToken = setToken; // alias
const setBearerToken = setToken; // alias
const getProfile = me; // alias
const get = api.get; // alias for direct axios usage
const apiClient = api; // alias for PaymentWidget and other components

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
  setAuthToken,
  setAxiosAuthToken,
  setBearerToken,
  getToken,
  setRefreshToken,
  getRefreshToken,
  clearToken,
  me,
  getProfile,
  login,
  get,
};

export default apiClient;
