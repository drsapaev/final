// frontend/src/api/client.js
// Unified axios-based API client wrapper for the frontend.
// Exports:
//  - api (axios instance)
//  - getApiBase()
//  - apiRequest(method, url, {params, data})
//  - setToken/getToken/clearToken
//  - me() - GET /me
//  - login(username, password) - POST /login (x-www-form-urlencoded)

import axios from 'axios';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';
const CSRF_BOOTSTRAP_ENABLED = import.meta.env.VITE_CSRF_BOOTSTRAP === '1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  // Optionally timeout: timeout: 15000,
});

// ✅ SECURITY: Check if token is expiring soon (within 5 minutes)
function isTokenExpiringSoon(token) {
  if (!token) return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return false;
    const payload = JSON.parse(atob(parts[1]));
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
let refreshPromise = null;
let pendingRequestsQueue = [];

/**
 * Refresh token with single-flight pattern.
 * All concurrent callers wait for the same promise, preventing multiple refresh calls.
 * @returns {Promise<string|null>} New access token or null on failure
 */
async function refreshTokenIfNeeded() {
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
      const response = await axios.post(`${API_BASE}/auth/refresh`, {
        refresh_token: refreshToken
      });

      if (response.data && response.data.access_token) {
        const newToken = response.data.access_token;
        tokenManager.setAccessToken(newToken);
        api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
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
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// ✅ SECURITY: Fetch CSRF token from server if not in cookie
let csrfTokenPromise = null;
let csrfEndpointUnavailable = false;
let csrfBootstrapSkippedLogged = false;
async function ensureCSRFToken() {
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
api.interceptors.request.use(async (config) => {
  // Try to refresh token if expiring soon (except for auth endpoints)
  if (!config.url?.includes('/auth/')) {
    await refreshTokenIfNeeded();
  }

  const token = tokenManager.getAccessToken();
  logger.log('🔍 [api/client.js] Request interceptor:', {
    url: config.url,
    hasToken: !!token,
    tokenPreview: token ? `${token.substring(0, 20)}...` : 'null',
    headers: config.headers
  });
  if (token) {
    const t = typeof token === 'string' ? token.trim() : token;
    if (t) {
      config.headers = config.headers || {};
      config.headers['Authorization'] = `Bearer ${t}`;
    }
  }

  // ✅ CSRF: Add X-CSRF-Token for state-changing requests
  const method = config.method?.toLowerCase();
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = await ensureCSRFToken();
    if (csrfToken) {
      config.headers = config.headers || {};
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }

  return config;
});

// ✅ SECURITY: Handle 401 responses - log but don't auto-clear tokens
// (prevents race condition where 401 during login transition clears new token)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      logger.warn('🔒 Unauthorized response received', {
        url: error.config?.url,
        hadToken: !!error.config?.headers?.Authorization
      });
      // NOTE: Token clearing removed to prevent race condition during login.
      // User will be redirected to login by RoleGuard or route protection instead.
    }
    return Promise.reject(error);
  }
);

function getApiBase() {
  return API_BASE;
}

function setToken(token) {
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

function getToken() {
  return tokenManager.getAccessToken();
}

function clearToken() {
  setToken(null);
}

/**
 * Generic request wrapper that normalizes server error detail.
 * Usage: await apiRequest('get', '/visits', { params: { limit: 10 } })
 */
async function apiRequest(method, url, { params = {}, data = {} } = {}) {
  try {
    const resp = await api.request({ method, url, params, data });
    return resp.data;
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
async function me() {
  // GET /auth/me
  const resp = await api.get('/auth/me');
  return resp.data;
}

/**
 * login: perform OAuth2 password flow (x-www-form-urlencoded).
 * Returns the server response (object with access_token, token_type).
 * Caller should call setToken(response.access_token) to persist.
 */
async function login(username, password) {
  const credentials = {
    username: username,
    password: password,
    remember_me: false
  };

  const resp = await api.post('/auth/login', credentials);

  return resp.data;
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
  getApiBase,
  apiRequest,
  setToken,
  setAuthToken,
  setAxiosAuthToken,
  setBearerToken,
  getToken,
  clearToken,
  me,
  getProfile,
  login,
  get,
};

export default apiClient;
