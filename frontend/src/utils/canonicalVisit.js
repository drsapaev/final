import logger from './logger';
// UX Audit: миграция raw fetch() → api/client.js.
import { api } from '../api/client';

export async function resolveCanonicalVisitId(appointmentId) {
  if (!appointmentId) {
    return null;
  }

  try {
    // UX Audit: api.get() автоматически добавляет Authorization header
    // через axios-interceptor. 401/403 обрабатываются централизованно.
    const response = await api.get(`/appointments/${appointmentId}/canonical-visit`);
    return response.data?.visit_id || null;
  } catch (error) {
    logger.warn('[canonical-visit] failed to resolve visit_id', {
      appointmentId,
      error: error?.message || 'unknown error'
    });
    return null;
  }
}
