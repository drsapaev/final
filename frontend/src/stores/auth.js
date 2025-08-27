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

import * as client from "../api/client.js";

const TOKEN_KEY = "auth_token";
const PROFILE_KEY = "auth_profile";

const subscribers = new Set();

function notify() {
  const state = getState();
  for (const s of subscribers) {
    try {
      s(state);
    } catch (e) {
      // swallow subscriber errors so one bad subscriber doesn't break others
      // but log for debugging.
      // eslint-disable-next-line no-console
      console.error("auth subscriber error:", e);
    }
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
    console.error("auth subscriber initial call error:", e);
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

/**
 * Set auth token locally and inform client (if compatible)
 * @param {string|null} token
 */
export function setToken(token) {
  try {
    if (token === null || token === undefined) {
      localStorage.removeItem(TOKEN_KEY);
    } else {
      localStorage.setItem(TOKEN_KEY, token);
    }
  } catch (e) {
    // ignore localStorage failures (e.g. private mode)
    console.warn("setToken localStorage failed:", e);
  }

  // If client provides a function to set auth token (name may vary), call it.
  try {
    if (typeof client.setAuthToken === "function") {
      client.setAuthToken(token);
    } else if (typeof client.setToken === "function") {
      // older name
      client.setToken(token);
    } else if (typeof client.setAxiosAuthToken === "function") {
      // some variants
      client.setAxiosAuthToken(token);
    } else if (typeof client.setBearerToken === "function") {
      client.setBearerToken(token);
    }
  } catch (e) {
    console.warn("client.setAuthToken call failed:", e);
  }

  // notify subscribers
  notify();
}

/**
 * Clear token & profile.
 */
export function clearToken() {
  setToken(null);
  setProfile(null);
}

/**
 * Fetch current user profile from API (if available).
 * Attempts client.me() or client.me (various names). Falls back to local storage.
 * @param {boolean} force - if true, refetch from server even if profile exists
 */
export async function getProfile(force = false) {
  const stored = getProfileFromStorage();
  if (!force && stored) return stored;

  // try several possible client-side exported helpers
  try {
    if (typeof client.me === "function") {
      const res = await client.me();
      if (res) {
        setProfile(res);
        return res;
      }
    } else if (typeof client.getProfile === "function") {
      const res = await client.getProfile();
      if (res) {
        setProfile(res);
        return res;
      }
    } else if (typeof client.api === "object" && typeof client.api.me === "function") {
      const res = await client.api.me();
      if (res) {
        setProfile(res);
        return res;
      }
    }
  } catch (err) {
    // don't throw — return local stored profile or null
    // eslint-disable-next-line no-console
    console.warn("getProfile: API call failed:", err);
  }

  return stored;
}

/**
 * Save profile to localStorage and notify subscribers.
 * @param {object|null} profile
 */
export function setProfile(profile) {
  try {
    if (profile === null || profile === undefined) {
      localStorage.removeItem(PROFILE_KEY);
    } else {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    }
  } catch (e) {
    console.warn("setProfile localStorage failed:", e);
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
  setProfile,
};

export default auth;
