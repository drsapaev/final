// frontend/src/api/auth.js
import { api, apiRequest } from "./client";

/**
 * Login (OAuth2 password flow) — returns resp.data (contains access_token)
 * Sends application/x-www-form-urlencoded as backend expects.
 */
export async function login(username, password) {
  if (!username || !password) throw new Error("username and password required");

  const body = new URLSearchParams();
  body.append("username", username);
  body.append("password", password);
  body.append("grant_type", "password");

  const resp = await api.request({
    method: "post",
    url: "/login", // client.api.baseURL includes /api/v1
    data: body.toString(),
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
  });
  return resp.data;
}

/** GET /me */
export async function me() {
  return apiRequest("get", "/me");
}

/** helper to set/remove Authorization header on api instance */
export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

/** logout local helper */
export function logout() {
  try {
    localStorage.removeItem("token");
    setAuthToken(null);
  } catch (e) {}
}
