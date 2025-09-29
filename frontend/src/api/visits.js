import { api } from './client';

/**
 * Получить визит по ID
 * GET /api/v1/visits/{visit_id}
 */
export async function getVisit(visitId) {
  const { data } = await api.get(`/visits/${encodeURIComponent(visitId)}`);
  return data;
}

/**
 * Перенести визит на произвольную дату/время.
 * POST /api/v1/visits/{visit_id}/reschedule
 * Тело запроса — то, что передаёшь в payload (например { date_str: "YYYY-MM-DD", time_str: "HH:MM" }).
 */
export async function rescheduleVisit(visitId, newDate) {
  const params = new URLSearchParams();
  if (newDate) params.set('new_date', newDate);
  const { data } = await api.post(
    `/visits/${encodeURIComponent(visitId)}/reschedule?${params.toString()}`
  );
  return data;
}

/**
 * Перенести визит на завтра.
 * POST /api/v1/visits/{visit_id}/reschedule/tomorrow
 */
export async function rescheduleTomorrow(visitId) {
  const { data } = await api.post(
    `/visits/${encodeURIComponent(visitId)}/reschedule/tomorrow`
  );
  return data;
}
