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

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  // Optionally timeout: timeout: 15000,
});

// Ensure Authorization header is attached for every request from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers = config.headers || {};
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

function getApiBase() {
  return API_BASE;
}

function setToken(token) {
  if (token) {
    localStorage.setItem('auth_token', token);
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    localStorage.removeItem('auth_token');
    delete api.defaults.headers.common['Authorization'];
  }
}

function getToken() {
  return localStorage.getItem('auth_token');
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
const existingToken = localStorage.getItem('auth_token');
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
