import { api } from './client';

/**
 * Получить визит по ID
 * GET /api/v1/visits/{visit_id}
 */
export async function getVisit(visitId) {
  const { data } = await api.get(`/visits/visits/${encodeURIComponent(visitId)}`);
  return data;
}

/**
 * Перенести визит на произвольную дату/время.
 * POST /api/v1/visits/visits/{visit_id}/reschedule
 * @param {number} visitId
 * @param {string} newDate — YYYY-MM-DD
 * @param {string} [newTime] — HH:MM (optional, R-27 fix)
 */
export async function rescheduleVisit(visitId, newDate, newTime) {
  const params = new URLSearchParams();
  if (newDate) params.set('new_date', newDate);
  if (newTime) params.set('new_time', newTime);
  const { data } = await api.post(
    `/visits/visits/${encodeURIComponent(visitId)}/reschedule?${params.toString()}`
  );
  return data;
}

/**
 * Перенести визит на завтра.
 * POST /api/v1/visits/visits/{visit_id}/reschedule/tomorrow
 */
export async function rescheduleTomorrow(visitId) {
  const { data } = await api.post(
    `/visits/visits/${encodeURIComponent(visitId)}/reschedule/tomorrow`
  );
  return data;
}
