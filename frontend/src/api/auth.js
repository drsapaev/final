// src/stores/auth.js
// Simple auth store used by UI components.
// Exports functions and `auth` object for compatibility with older imports.

import { me, setAuthToken } from "../api/client.js";

const TOKEN_KEY = "auth_token";
const PROFILE_KEY = "auth_profile";

let token = null;
let profile = null;
const listeners = new Set();

/** Initialize from localStorage */
try {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) {
    token = t;
    // ensure axios header is set
    if (typeof setAuthToken === "function") setAuthToken(token);
  }
  const p = localStorage.getItem(PROFILE_KEY);
  if (p) {
    profile = JSON.parse(p);
  }
} catch {
  // ignore
}

/** Subscribe / unsubscribe */
export function subscribe(fn) {
  listeners.add(fn);
  try {
    fn(getState());
  } catch {}
  return () => unsubscribe(fn);
}

export function unsubscribe(fn) {
  listeners.delete(fn);
}

function notify() {
  const s = getState();
  for (const fn of listeners) {
    try {
      fn(s);
    } catch {}
  }
}

/** Token accessors */
export function getToken() {
  return token;
}

/** Set token locally and sync axios header */
export function setToken(nextToken) {
  token = nextToken || null;
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {}
  if (typeof setAuthToken === "function") setAuthToken(token);
  notify();
}

/** Clear token and profile */
export function clearToken() {
  token = null;
  profile = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
  } catch {}
  if (typeof setAuthToken === "function") setAuthToken(null);
  notify();
}

/** Profile helpers */
export function getProfileSync() {
  return profile;
}

export function setProfile(nextProfile) {
  profile = nextProfile || null;
  try {
    if (profile) {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    } else {
      localStorage.removeItem(PROFILE_KEY);
    }
  } catch {}
  notify();
}

/**
 * Fetch profile from backend (GET /me)
 * If force=false and profile exists, returns cached value.
 */
export async function getProfile(force = false) {
  if (!force && profile) return profile;
  const t = getToken();
  if (!t) {
    clearToken();
    throw new Error("Not authenticated");
  }
  // ensure axios header is set
  if (typeof setAuthToken === "function") setAuthToken(t);
  const data = await me(); // may throw
  setProfile(data);
  return profile;
}

/** Snapshot of current state */
export function getState() {
  return {
    token,
    profile,
    isAuthenticated: !!token,
  };
}

/** Backwards/compatibility object */
export const auth = {
  subscribe,
  unsubscribe,
  getToken,
  setToken,
  clearToken,
  getProfile,
  getProfileSync,
  setProfile,
  getState,
};

export default auth;
