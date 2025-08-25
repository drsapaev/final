// Очередь/статистика по дням
import { apiRequest } from "./client";

/**
 * Открыть онлайн-очередь (ровно как в Swagger):
 * POST /online-queue/open
 * query: department (str), date_str (YYYY-MM-DD), start_number (int>=0)
 */
export async function openQueue(department, date_str, start_number = 0) {
  if (!department) throw new Error("department is required");
  if (!date_str) throw new Error("date_str is required");
  const params = { department, date_str, start_number };
  // тело не передаём — только query, чтобы не ловить 422
  return apiRequest("POST", "/online-queue/open", { params });
}

/**
 * Получить статистику на день.
 * В проекте есть два варианта: /appointments/stats и /online-queue/stats.
 * Пробуем сначала /appointments/stats с параметрами {department, d}, если 404 или 422 — пытаемся /online-queue/stats
 */
export async function getQueueStats(department, date) {
  const params1 = {};
  if (department) params1.department = department;
  if (date) params1.d = date;

  try {
    return await apiRequest("GET", "/appointments/stats", { params: params1 });
  } catch (e) {
    // попробуем alternative: /online-queue/stats; иногда параметр может называться date_str
    const params2 = { ...(department ? { department } : {}) };
    if (date) params2.date_str = date;
    try {
      return await apiRequest("GET", "/online-queue/stats", { params: params2 });
    } catch {
      // вернём пустую структуру, чтобы не падал UI
      return { items: [], total: 0 };
    }
  }
}

