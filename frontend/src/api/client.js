// Minimal, dependency-free API client for Clinic Queue Manager
// - Keeps token in localStorage
// - Handles JSON + x-www-form-urlencoded
// - Throws rich errors { status, data } on non-2xx

const TOKEN_KEY = "auth_token";

export function getApiBase() {
  // Example: http://localhost:8000/api/v1
  const base = import.meta?.env?.VITE_API_BASE || "http://localhost:8000/api/v1";
  return String(base).replace(/\/+$/, "");
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export function clearToken() {
  setToken(null);
}

function buildUrl(path, params) {
  const base = getApiBase();
  const cleanPath = String(path || "").startsWith("/") ? path : `/${path || ""}`;
  const url = new URL(base + cleanPath);
  if (params && typeof params === "object") {
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      url.searchParams.set(k, String(v));
    });
  }
  return url.toString();
}

function normalizeHeaders(h) {
  const headers = new Headers(h || {});
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  return headers;
}

export async function apiRequest(method, path, { params, body, headers } = {}) {
  const url = buildUrl(path, params);
  const token = getToken();
  const hdrs = normalizeHeaders(headers);

  let fetchBody = body;
  if (body instanceof FormData) {
    // Let browser set Content-Type with boundary
  } else if (body && typeof body === "object" && !(body instanceof URLSearchParams)) {
    if (!hdrs.has("Content-Type")) hdrs.set("Content-Type", "application/json");
    fetchBody = JSON.stringify(body);
  } else if (body instanceof URLSearchParams) {
    if (!hdrs.has("Content-Type")) hdrs.set("Content-Type", "application/x-www-form-urlencoded");
  }

  if (token && !hdrs.has("Authorization")) {
    hdrs.set("Authorization", `Bearer ${token}`);
  }

  const resp = await fetch(url, {
    method: method.toUpperCase(),
    headers: hdrs,
    body: ["GET", "HEAD"].includes(method.toUpperCase()) ? undefined : fetchBody,
    credentials: "omit",
  });

  const contentType = resp.headers.get("content-type") || "";
  let data = null;
  try {
    if (contentType.includes("application/json")) {
      data = await resp.json();
    } else if (contentType.includes("application/pdf")) {
      data = await resp.arrayBuffer();
    } else if (contentType.includes("text/")) {
      data = await resp.text();
    } else {
      // fallback
      data = await resp.arrayBuffer();
    }
  } catch {
    data = null;
  }

  if (!resp.ok) {
    const err = new Error(`HTTP ${resp.status}`);
    err.status = resp.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (path, opts) => apiRequest("GET", path, opts),
  post: (path, opts) => apiRequest("POST", path, opts),
  put: (path, opts) => apiRequest("PUT", path, opts),
  del: (path, opts) => apiRequest("DELETE", path, opts),
};

// ---- Auth helpers ----

export async function login(username, password) {
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", password);
  // keep OAuth2 fields present but empty for FastAPI form
  form.set("grant_type", "");
  form.set("scope", "");
  form.set("client_id", "");
  form.set("client_secret", "");
  const res = await apiRequest("POST", "/auth/login", { body: form });
  // Expecting { access_token, token_type }
  const token = res?.access_token;
  if (!token) {
    const e = new Error("No access_token in response");
    e.data = res;
    throw e;
  }
  return token;
}

export async function me() {
  return apiRequest("GET", "/auth/me");
}