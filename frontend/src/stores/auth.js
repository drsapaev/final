// src/stores/auth.js
// Lightweight auth store used across the frontend.
// - Keeps token/profile in localStorage
// - Notifies subscribers on changes
// - Provides compatibility aliases for historical imports
//
// This file is intentionally defensive: it imports the API client as a namespace
// (`* as client`) so missing individual named exports in client.js won't cause
// an immediate import-time crash. We attempt to call client.me()/client.setAuthToken
// only when they exist.
//
// Exports:
//   subscribe, getState, getToken, setToken, clearToken, getProfile, setProfile
//   (and a default `auth` object)
// Backwards-compatible aliases:
//   setAuthToken, getAuthToken, clearAuthToken, setAuthProfile, subscribeAuth
//
// Keep changes minimal and additive — don't remove existing exported names.

import { me, setToken as setClientToken } from '../api/client.js';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
const TOKEN_KEY = 'auth_token';
const PROFILE_KEY = 'auth_profile';
const SESSION_VALIDATION_CACHE_MS = 30_000;

const subscribers = new Set();
let profileLoadPromise = null;
let sessionValidationPromise = null;
let lastValidatedAt = 0;
let lastValidatedToken = null;

function notify() {
  const state = getState();
  for (const s of subscribers) {
    try {
      s(state);
    } catch (e) {
      // swallow subscriber errors so one bad subscriber doesn't break others
      // but log for debugging.

      logger.error('auth subscriber error:', e);
    }
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('authStateChanged', { detail: state }));
  }
}

/**
 * Subscribe to auth changes.
 * @param {(state: {token:string|null, profile:object|null}) => void} fn
 * @returns {()=>void} unsubscribe
 */
export function subscribe(fn) {
  subscribers.add(fn);
  // call immediately with current state
  try {
    fn(getState());
  } catch (e) {
    logger.error('auth subscriber initial call error:', e);
  }
  return () => subscribers.delete(fn);
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getProfileFromStorage() {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function getState() {
  return {
    token: getToken(),
    profile: getProfileFromStorage(),
  };
}

function clearProfileStorageOnly() {
  try {
    localStorage.removeItem(PROFILE_KEY);
  } catch (e) {
    logger.warn('clearProfileStorageOnly failed:', e);
  }
}

/**
 * Set auth token locally and inform client (if compatible)
 * @param {string|null} token
 */
export function setToken(token) {
  const previousToken = getToken();

  try {
    if (token === null || token === undefined) {
      localStorage.removeItem(TOKEN_KEY);
    } else {
      localStorage.setItem(TOKEN_KEY, token);
    }
  } catch (e) {
    // ignore localStorage failures (e.g. private mode)
    logger.warn('setToken localStorage failed:', e);
  }

  // Синхронизируем токен с API клиентом
  try {
    if (typeof setClientToken === 'function') {
      setClientToken(token);
    }
  } catch (e) {
    logger.warn('client.setToken call failed:', e);
  }

  if (previousToken !== token) {
    profileLoadPromise = null;
    sessionValidationPromise = null;
    lastValidatedAt = 0;
    lastValidatedToken = token || null;
  }

  // notify subscribers
  notify();
}

/**
 * Clear token & profile.
 */
export function clearToken() {
  profileLoadPromise = null;
  sessionValidationPromise = null;
  lastValidatedAt = 0;
  lastValidatedToken = null;

  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch (e) {
    logger.warn('clearToken localStorage failed:', e);
  }
  clearProfileStorageOnly();
  tokenManager.setUserData(null);

  try {
    if (typeof setClientToken === 'function') {
      setClientToken(null);
    }
  } catch (e) {
    logger.warn('client.setToken(null) call failed:', e);
  }

  logger.info('[FIX:AUTH] Cleared auth token and profile from local storage');
  notify();
}

/**
 * Fetch current user profile from API (if available).
 * Attempts client.me() or client.me (various names). Falls back to local storage.
 * @param {boolean} force - if true, refetch from server even if profile exists
 */
export async function getProfile(force = false) {
  const token = getToken();
  const stored = getProfileFromStorage();
  if (!token) {
    if (stored) {
      logger.warn('[FIX:AUTH] Profile exists without token, clearing stale auth state');
      clearToken();
    }
    return null;
  }
  if (!force && stored) return stored;
  if (profileLoadPromise) return profileLoadPromise;

  // Используем централизованный API клиент
  profileLoadPromise = (async () => {
    try {
      if (typeof me === 'function') {
        const res = await me();
        if (res) {
          setProfile(res);
          logger.info('[FIX:AUTH] Loaded auth profile from backend');
          return res;
        }
      }
    } catch (err) {
      const status = err?.response?.status;
      if (status === 401 || status === 403) {
        logger.warn('[FIX:AUTH] Backend rejected current session, clearing auth state', {
          status,
        });
        clearToken();
        return null;
      }
      if (status === 429) {
        logger.warn('[FIX:AUTH] Auth profile check hit rate limit, keeping cached auth state', {
          status,
        });
        return stored;
      }
      // don't throw — return local stored profile or null
      logger.warn('getProfile: API call failed:', err);
    } finally {
      profileLoadPromise = null;
    }
    return stored;
  })();

  return profileLoadPromise;
}

export async function validateSession(force = false) {
  const token = getToken();
  if (!token) {
    lastValidatedAt = 0;
    lastValidatedToken = null;
    return getState();
  }

  if (!tokenManager.isTokenValid()) {
    logger.warn('[FIX:AUTH] Detected expired or malformed token before route render');
    clearToken();
    return getState();
  }

  const storedProfile = getProfileFromStorage();
  const now = Date.now();
  const hasRecentValidation = (
    !force &&
    Boolean(storedProfile) &&
    lastValidatedToken === token &&
    now - lastValidatedAt < SESSION_VALIDATION_CACHE_MS
  );

  if (hasRecentValidation) {
    logger.info('[FIX:AUTH] Reusing recent auth session validation', {
      ageMs: now - lastValidatedAt,
    });
    return {
      token,
      profile: storedProfile,
    };
  }

  if (sessionValidationPromise) {
    return sessionValidationPromise;
  }

  sessionValidationPromise = (async () => {
    const shouldRefetch = force || !storedProfile;
    const profile = await getProfile(shouldRefetch);
    const nextToken = getToken();

    if (nextToken) {
      lastValidatedAt = Date.now();
      lastValidatedToken = nextToken;
    } else {
      lastValidatedAt = 0;
      lastValidatedToken = null;
    }

    return {
      token: nextToken,
      profile,
    };
  })();

  try {
    return await sessionValidationPromise;
  } finally {
    sessionValidationPromise = null;
  }
}

/**
 * Save profile to localStorage and notify subscribers.
 * @param {object|null} profile
 */
export function setProfile(profile) {
  try {
    if (profile === null || profile === undefined) {
      localStorage.removeItem(PROFILE_KEY);
      tokenManager.setUserData(null);
    } else {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
      tokenManager.setUserData(profile);
    }
  } catch (e) {
    logger.warn('setProfile localStorage failed:', e);
  }
  notify();
}

// Backwards-compatible names (aliases)
export const setAuthToken = setToken;
export const getAuthToken = getToken;
export const clearAuthToken = clearToken;
export const setAuthProfile = setProfile;
export const subscribeAuth = subscribe;

// Default export for consumers using default import
const auth = {
  subscribe,
  getState,
  getToken,
  setToken,
  clearToken,
  getProfile,
  validateSession,
  setProfile,
};

export default auth;
