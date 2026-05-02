import logger from '../utils/logger';
import { buildApiUrl } from './runtime';

const SETUP_STATUS_CACHE_MS = 30_000;

let setupStatusCache = null;
let setupStatusCacheAt = 0;
let setupStatusRequestPromise = null;

async function parseJsonResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload?.detail || payload?.message || 'Setup request failed';
    throw new Error(detail);
  }

  return payload;
}

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
      const response = await fetch(buildApiUrl('/setup/status'));
      const payload = await parseJsonResponse(response);
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
      throw error;
    } finally {
      setupStatusRequestPromise = null;
    }
  })();

  return setupStatusRequestPromise;
}

export async function initializeSetup(payload) {
  const response = await fetch(buildApiUrl('/setup/initialize'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  const result = await parseJsonResponse(response);
  clearSetupStatusCache();
  return result;
}
