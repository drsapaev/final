// src/stores/auth.ts
// Lightweight auth store used across the frontend.
// - Keeps token/profile in sessionStorage
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

import { me, setToken as setClientToken } from '../api/client';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';
import type { AuthState, UserProfile } from '../types/domain/auth';
import { safeJsonParse } from '../utils/safeJsonParse';
import type { HttpApiError } from '../types/errors';

// Wave G6: removed `export type { AuthState, UserProfile } from '../types/domain/auth'`
// re-export shim. Consumers should import AuthState directly from
// '@/types/domain/auth'. The stores/auth.ts module still imports these
// types for its own internal use (getState return type, subscriber type).

type AuthSubscriber = (state: AuthState) => void;

const TOKEN_KEY = 'auth_token';
const PROFILE_KEY = 'auth_profile';
const SESSION_VALIDATION_CACHE_MS = 30_000;

const subscribers = new Set<AuthSubscriber>();
let profileLoadPromise: Promise<UserProfile | null> | null = null;
let sessionValidationPromise: Promise<AuthState> | null = null;
let lastValidatedAt = 0;
let lastValidatedToken: string | null = null;

function notify(): void {
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
 * @param fn subscriber called with the current AuthState on subscribe
 *   and on every subsequent change.
 * @returns unsubscribe
 */
export function subscribe(fn: AuthSubscriber): () => void {
  subscribers.add(fn);
  // call immediately with current state
  try {
    fn(getState());
  } catch (e) {
    logger.error('auth subscriber initial call error:', e);
  }
  return () => {
    subscribers.delete(fn);
  };
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getProfileFromStorage(): UserProfile | null {
  try {
    const raw = sessionStorage.getItem(PROFILE_KEY);
    return raw ? (safeJsonParse(raw) as UserProfile) : null;
  } catch {
    return null;
  }
}

export function getState(): AuthState {
  return {
    token: getToken(),
    profile: getProfileFromStorage(),
  };
}

function clearProfileStorageOnly(): void {
  try {
    sessionStorage.removeItem(PROFILE_KEY);
  } catch (e) {
    logger.warn('clearProfileStorageOnly failed:', e);
  }
}

/**
 * Set auth token locally and inform client (if compatible)
 * @param token new token value (null to clear)
 */
export function setToken(token: string | null): void {
  const previousToken = getToken();

  try {
    if (token === null || token === undefined) {
      sessionStorage.removeItem(TOKEN_KEY);
    } else {
      sessionStorage.setItem(TOKEN_KEY, token);
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
export function clearToken(): void {
  profileLoadPromise = null;
  sessionValidationPromise = null;
  lastValidatedAt = 0;
  lastValidatedToken = null;

  try {
    sessionStorage.removeItem(TOKEN_KEY);
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

  // audit/phase-2, BS-37 + BS-38: clear PHI/financial + patient-side keys
  // that previously survived staff logout. Without this block, on a shared
  // kiosk the next user could read previous user's data:
  //   - admin_finance_transactions_cache: holds { patient_id, amount,
  //     payment_method, patient_name, ... } — PHI + financial. Stored in
  //     localStorage which persists across tab/browser restarts.
  //   - cache_*: generic useCachedData writes arbitrary API responses
  //     (potentially patient lists) to localStorage.
  //   - patient_jwt_token / patient_refresh_token / patient_token_expires_at:
  //     written by useTelegramAuth/useWebAuthn directly to sessionStorage,
  //     bypassing tokenManager. Staff logout didn't touch them, so patient
  //     Mini-App identity lingered after a staff session.
  // Removing these keys is idempotent and safe — none are needed for the
  // logout flow itself.
  try {
    localStorage.removeItem('admin_finance_transactions_cache');
    // Sweep any cache_* keys written by useCachedData (useApi.ts).
    // We do not enumerate ALL localStorage keys here because that would
    // also clear unrelated app state (e.g., saved UI preferences); the
    // cache_* prefix is specific to useCachedData.
    const cacheKeys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('cache_')) {
        cacheKeys.push(key);
      }
    }
    cacheKeys.forEach((k) => localStorage.removeItem(k));
  } catch (e) {
    logger.warn('clearToken localStorage PHI/financial sweep failed:', e);
  }

  try {
    sessionStorage.removeItem('patient_jwt_token');
    sessionStorage.removeItem('patient_refresh_token');
    sessionStorage.removeItem('patient_token_expires_at');
  } catch (e) {
    logger.warn('clearToken sessionStorage patient-token sweep failed:', e);
  }

  logger.info('[FIX:AUTH] Cleared auth token, profile, PHI/financial cache, and patient tokens');
  notify();
}

/**
 * Fetch current user profile from API (if available).
 * Attempts client.me() or client.me (various names). Falls back to local storage.
 * @param force if true, refetch from server even if profile exists
 */
export async function getProfile(force = false): Promise<UserProfile | null> {
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
  profileLoadPromise = (async (): Promise<UserProfile | null> => {
    try {
      if (typeof me === 'function') {
        const res = (await me()) as UserProfile | null;
        if (res) {
          setProfile(res);
          logger.info('[FIX:AUTH] Loaded auth profile from backend');
          return res;
        }
      }
    } catch (err) {
      const e = err as HttpApiError;
      const status = e?.response?.status;

      // #05 Tier 1: Distinguish CSRF 403 from authorization 403.
      // A CSRF rejection (X-CSRF-Status: rejected header) is recoverable —
      // the axios response interceptor handles it by refreshing the CSRF
      // token and retrying. We must NOT clear auth state (logout) for CSRF 403.
      // Only clear auth on 401 or a genuine authorization 403 (no CSRF header).
      const isCSRFRejection =
        status === 403 &&
        (e?.response?.headers?.['x-csrf-status'] === 'rejected' ||
         e?.response?.headers?.['X-CSRF-Status'] === 'rejected');

      if (status === 401 || (status === 403 && !isCSRFRejection)) {
        logger.warn('[FIX:AUTH] Backend rejected current session, clearing auth state', {
          status,
          isCSRF: isCSRFRejection,
        });
        clearToken();
        return null;
      }
      if (status === 403 && isCSRFRejection) {
        // CSRF rejection — don't logout. The interceptor should have retried.
        // If we get here, the retry also failed, but we still don't clear auth.
        logger.warn('[FIX:AUTH] CSRF rejection during profile fetch — keeping auth state', {
          status,
        });
        return stored;
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

export async function validateSession(force = false): Promise<AuthState> {
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

  sessionValidationPromise = (async (): Promise<AuthState> => {
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
 * Save profile to sessionStorage and notify subscribers.
 * @param profile new profile value (null to clear)
 */
export function setProfile(profile: UserProfile | null): void {
  try {
    if (profile === null || profile === undefined) {
      sessionStorage.removeItem(PROFILE_KEY);
      tokenManager.setUserData(null);
    } else {
      sessionStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
      tokenManager.setUserData(profile as Record<string, unknown>);
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
