// frontend/src/api/client.js
// Unified axios-based API client wrapper for the frontend.
// Exports:
//  - api (axios instance)
//  - getApiBase()
//  - apiRequest(method, url, {params, data})
//  - setToken/getToken/clearToken
//  - me() - GET /me
//  - login(username, password) - POST /login (x-www-form-urlencoded)

import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  // Optionally timeout: timeout: 15000,
});

function getApiBase() {
  return API_BASE;
}

function setToken(token) {
  if (token) {
    localStorage.setItem("auth_token", token);
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    localStorage.removeItem("auth_token");
    delete api.defaults.headers.common["Authorization"];
  }
}

function getToken() {
  return localStorage.getItem("auth_token");
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
  // GET /me
  const resp = await api.get("/me");
  return resp.data;
}

/**
 * login: perform OAuth2 password flow (x-www-form-urlencoded).
 * Returns the server response (object with access_token, token_type).
 * Caller should call setToken(response.access_token) to persist.
 */
async function login(username, password) {
  const params = new URLSearchParams();
  params.append("username", username);
  params.append("password", password);
  params.append("grant_type", "password");

  const resp = await api.post("/login", params.toString(), {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return resp.data;
}

// Backwards-compatible alias expected by older frontend code
const setAuthToken = setToken; // alias

export {
  api,
  getApiBase,
  apiRequest,
  setToken,
  setAuthToken,
  getToken,
  clearToken,
  me,
  login,
};
