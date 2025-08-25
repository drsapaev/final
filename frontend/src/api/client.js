// Axios-клиент для Clinic App
// • База берётся из VITE_API_BASE (например, "/api/v1" через Vite proxy или абсолютный URL)
// • Единая обработка ошибок: detail из response.data.detail (если есть)
// • Авторизация: по возможности подставляем Bearer из localStorage("auth_token")
// • Экспорт: api (axios), apiRequest, getApiBase, login, me

import axios from "axios";

export function getApiBase() {
  const raw = (import.meta?.env?.VITE_API_BASE ?? "/api/v1").toString().trim();
  return raw; // поддерживает и относительный, и абсолютный URL
}

export const api = axios.create({
  baseURL: getApiBase(),
  withCredentials: true,
});

// optional Bearer из localStorage (если используешь токен)
api.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers = config.headers || {};
      if (!config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
  } catch {}
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const status = error?.response?.status;
    const data = error?.response?.data;
    const detail =
      (typeof data?.detail === "string" && data.detail) ||
      (Array.isArray(data?.detail) && data.detail.map((d) => d?.msg).filter(Boolean).join("; ")) ||
      data?.message ||
      error.message ||
      "Request failed";
    const err = new Error(detail);
    err.status = status;
    err.data = data;
    throw err;
  }
);

// Унифицированная обёртка (совместима с прежним apiRequest)
export async function apiRequest(method, path, { params, json, body, headers, signal } = {}) {
  const config = {
    url: path,
    method,
    params,
    headers: { ...(headers || {}) },
    signal,
  };

  if (json !== undefined) {
    config.data = json;
    config.headers["Content-Type"] = "application/json";
  } else if (body !== undefined) {
    config.data = body; // FormData/URLSearchParams — без ручного Content-Type
  }

  const resp = await api.request(config);
  return resp?.data ?? {};
}

// Удобные вызовы авторизации (если нужны)
export async function login({
  username,
  password,
  grant_type = "password",
  client_id = "",
  client_secret = "",
  scope = "",
} = {}) {
  const form = new URLSearchParams();
  if (username !== undefined) form.set("username", String(username));
  form.set("password", String(password || ""));
  form.set("grant_type", grant_type);
  form.set("client_id", client_id);
  form.set("client_secret", client_secret);
  form.set("scope", scope);

  const resp = await api.post("/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return resp.data; // ожидаем { access_token, ... }
}

export async function me() {
  const resp = await api.get("/me");
  return resp.data;
}

