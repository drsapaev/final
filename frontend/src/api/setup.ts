import logger from '../utils/logger';
// UX Audit Setup bugfix: миграция с raw fetch() на api/client.js.
// Раньше здесь было 2 raw fetch() вызова к /setup/status и /setup/initialize
// с ручным JSON-parsing и error-handling.
// Теперь auth/CSRF/refresh-token обрабатываются централизованно через
// axios-interceptor в api/client.js. Это особенно важно для /setup/initialize,
// потому что это pre-auth endpoint, но всё равно нужен unified error handling
// (network errors, 500s, timeout).
import { api } from './client';

const SETUP_STATUS_CACHE_MS = 30_000;

let setupStatusCache = null;
let setupStatusCacheAt = 0;
let setupStatusRequestPromise = null;

export function clearSetupStatusCache() {
  setupStatusCache = null;
  setupStatusCacheAt = 0;
}

export async function fetchSetupStatus() {
  const now = Date.now();
  if (setupStatusCache && now - setupStatusCacheAt < SETUP_STATUS_CACHE_MS) {
    logger.info('[FIX:SETUP] Using cached setup status snapshot', {
      ageMs: now - setupStatusCacheAt,
    });
    return setupStatusCache;
  }

  if (setupStatusRequestPromise) {
    logger.info('[FIX:SETUP] Reusing in-flight setup status request');
    return setupStatusRequestPromise;
  }

  setupStatusRequestPromise = (async () => {
    try {
      // UX Audit Setup bugfix: raw fetch() → api.get().
      // Axios сам парсит JSON и бросает Error с detail при не-2xx.
      const response = await api.get('/setup/status');
      const payload = response.data;
      setupStatusCache = payload;
      setupStatusCacheAt = Date.now();
      return payload;
    } catch (error) {
      if (setupStatusCache) {
        logger.warn('[FIX:SETUP] Setup status request failed, falling back to cached value', {
          error: error?.message || 'unknown error',
        });
        return setupStatusCache;
      }
      // Нормализуем error message из axios response.
      const detail = error?.response?.data?.detail || error?.message || 'Setup status request failed';
      throw new Error(detail);
    } finally {
      setupStatusRequestPromise = null;
    }
  })();

  return setupStatusRequestPromise;
}

export async function initializeSetup(payload) {
  // UX Audit Setup bugfix: raw fetch() POST → api.post().
  // Axios автоматически ставит Content-Type: application/json и парсит ответ.
  try {
    const response = await api.post('/setup/initialize', payload);
    clearSetupStatusCache();
    return response.data;
  } catch (error) {
    // Нормализуем error message из axios response.
    const detail = error?.response?.data?.detail || error?.message || 'Setup request failed';
    throw new Error(detail);
  }
}
