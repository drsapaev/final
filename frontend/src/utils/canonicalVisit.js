import logger from './logger';
import { buildApiUrl } from '../api/runtime';
import tokenManager from './tokenManager';

export async function resolveCanonicalVisitId(appointmentId) {
  if (!appointmentId) {
    return null;
  }

  const token = tokenManager.getAccessToken();
  if (!token) {
    return null;
  }

  try {
    const response = await fetch(buildApiUrl(`/appointments/${appointmentId}/canonical-visit`), {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
    return payload?.visit_id || null;
  } catch (error) {
    logger.warn('[canonical-visit] failed to resolve visit_id', {
      appointmentId,
      error: error?.message || 'unknown error'
    });
    return null;
  }
}
