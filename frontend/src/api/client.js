// unified client for frontend
// exports: api (axios instance), apiRequest(fn), getApiBase()
import axios from "axios";

const DEFAULT_BASE = "http://localhost:8000/api/v1";
const BASE = import.meta.env.VITE_API_BASE || DEFAULT_BASE;

/**
 * axios instance (named export `api`)
 * Base must point to host + prefix, for example: http://localhost:8000/api/v1
 */
export const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

/**
 * Response interceptor: try to produce human-friendly message from response.data.detail
 */
api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err && err.response && err.response.data) {
      const d = err.response.data;
      if (d.detail) {
        // unify detail -> string
        try {
          if (typeof d.detail === "string") {
            err.message = d.detail;
          } else if (Array.isArray(d.detail)) {
            // array of {loc,msg,type} or strings
            err.message = d.detail
              .map((it) => {
                if (typeof it === "string") return it;
                if (it.msg) return it.msg;
                return JSON.stringify(it);
              })
              .join("; ");
          } else {
            err.message = JSON.stringify(d.detail);
          }
        } catch (e) {
          // fallback
          err.message = "API request failed";
        }
      }
    }
    return Promise.reject(err);
  }
);

/**
 * Simple wrapper used across the app
 * method: 'get'|'post'|...
 * path: relative path (e.g. '/visits' or '/online-queue/open') — axios will prefix with baseURL
 * options: { params, data, headers }
 */
export async function apiRequest(method, path, options = {}) {
  const { params, data, headers } = options;
  const resp = await api.request({
    method,
    url: path,
    params,
    data,
    headers,
  });
  return resp.data;
}

export function getApiBase() {
  return BASE;
}
