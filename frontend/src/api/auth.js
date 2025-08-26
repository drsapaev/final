// frontend/src/api/auth.js
// Auth helper functions. Use api / apiRequest from client.js

import { api, apiRequest, getApiBase } from "./client";

/**
 * Login with OAuth2 password flow (x-www-form-urlencoded).
 * Backend expects: username, password, grant_type=password
 *
 * Returns the parsed response data (should contain access_token etc.)
 */
export async function login(username, password) {
  if (!username || !password) {
    throw new Error("username and password required");
  }

  // build form body for OAuth2 password flow
  const body = new URLSearchParams();
  body.append("username", username);
  body.append("password", password);
  body.append("grant_type", "password");

  try {
    const resp = await api.request({
      method: "post",
      url: "/login", // client.api.baseURL already contains /api/v1 if configured
      data: body.toString(),
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json",
      },
    });

    // resp.data expected like { access_token, token_type, ... }
    return resp.data;
  } catch (err) {
    // api interceptor in client.js already normalizes error.message from response.data.detail
    throw err;
  }
}

/**
 * Get current user profile (GET /me)
 */
export async function me() {
  return apiRequest("get", "/me");
}

/**
 * Logout helper (client-side); remove stored token if you store it in localStorage
 */
export function logout() {
  try {
    localStorage.removeItem("token");
  } catch (e) {
    // ignore
  }
}

/**
 * Helper to set Authorization header for api instance (optional)
 */
export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

export { getApiBase };
