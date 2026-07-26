import { api } from './client';
import type { VisitDto, VisitWithServicesDto } from '../types/api';

/**
 * Получить визит по ID
 * GET /api/v1/visits/visits/{visit_id}
 *
 * Returns the VisitWithServices envelope (visit + services). The endpoint
 * historically returned this richer shape even for single-visit fetches;
 * keeping it preserves backwards compatibility for callers that read
 * `result.visit` and `result.services`.
 */
export async function getVisit(visitId: string | number): Promise<VisitWithServicesDto> {
  const { data } = await api.get<VisitWithServicesDto>(`/visits/visits/${encodeURIComponent(visitId)}`);
  return data;
}

/**
 * Перенести визит на произвольную дату/время.
 * POST /api/v1/visits/visits/{visit_id}/reschedule
 * @param visitId
 * @param newDate — YYYY-MM-DD
 * @param newTime — HH:MM (optional, R-27 fix)
 */
export async function rescheduleVisit(
  visitId: string | number,
  newDate: string,
  newTime?: string,
): Promise<VisitDto> {
  const params = new URLSearchParams();
  if (newDate) params.set('new_date', newDate);
  if (newTime) params.set('new_time', newTime);
  const { data } = await api.post<VisitDto>(
    `/visits/visits/${encodeURIComponent(visitId)}/reschedule?${params.toString()}`
  );
  return data;
}

/**
 * Перенести визит на завтра.
 * POST /api/v1/visits/visits/{visit_id}/reschedule/tomorrow
 */
export async function rescheduleTomorrow(visitId: string | number): Promise<VisitDto> {
  const { data } = await api.post<VisitDto>(
    `/visits/visits/${encodeURIComponent(visitId)}/reschedule/tomorrow`
  );
  return data;
}
