// frontend/src/api/client.js
import axios from "axios";

const DEFAULT_BASE = "http://localhost:8000/api/v1";
const BASE = import.meta.env.VITE_API_BASE || DEFAULT_BASE;

export const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err && err.response && err.response.data) {
      const d = err.response.data;
      if (d.detail) {
        try {
          if (typeof d.detail === "string") {
            err.message = d.detail;
          } else if (Array.isArray(d.detail)) {
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
          err.message = "API request failed";
        }
      }
    }
    return Promise.reject(err);
  }
);

/**
 * apiRequest(method, path, {params, data, headers})
 * path = relative path after baseURL, e.g. "/me" or "/visits"
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
