// src/api/health.js
// Утилиты для простого health-check'а бэкенда и статуса активации.

import { api, getApiBase } from "./client";

/**
 * Проверка "жив ли" бэкенд.
 * Ходим на {ORIGIN}/openapi.json (без /api/v1), чтобы не ловить 404.
 * Возвращаем компактный объект, чтобы UI не падал.
 */
export async function getHealth() {
  try {
    const base = String(getApiBase?.() ?? "");
    const origin = base.replace(/\/api\/v\d+$/i, ""); // http://localhost:8000
    const res = await fetch(`${origin}/openapi.json`, {
      headers: { Accept: "application/json" },
    });
    return { ok: res.ok, status: res.status };
  } catch (e) {
    return {
      ok: false,
      error:
        e?.message ??
        (typeof e === "string" ? e : "getHealth: unreachable/openapi.json"),
    };
  }
}

/**
 * Статус активации системы.
 * Если эндпоинта нет — возвращаем { ok:false, detail: ... }, чтобы страница не падала.
 */
export async function getActivationStatus() {
  try {
    const { data } = await api.get("/activation/status");
    return data;
  } catch (e) {
    const detail =
      e?.response?.data?.detail ??
      e?.message ??
      "activation/status not available";
    return { ok: false, detail };
  }
}
