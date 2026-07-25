import { api } from './client';
import type {
  QueueSpecialist,
  QueueData,
  QueuePayload,
  QrData,
  QueueActionResponse,
  QueueJoinSessionData,
  QrTokenInfo,
  QueueProfilesResponse,
} from '../types/domain/queue';
import {
  mapQueueSpecialistDtos,
  mapQueueDataDto,
  mapQueuePayloadDto,
  mapQrDataDto,
  mapQueueActionResponseDto,
} from './mappers';

const withParams = (params: Record<string, unknown>): Record<string, unknown> =>
  Object.fromEntries(
    Object.entries(params || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );

export async function fetchAvailableSpecialists(): Promise<QueueSpecialist[]> {
  const response = await api.get('/queue/available-specialists');
  const payload = response.data?.specialists ?? response.data ?? [];
  return mapQueueSpecialistDtos(payload);
}

export async function fetchPublicQueueProfiles(): Promise<QueueProfilesResponse> {
  const response = await api.get('/queues/profiles/public');
  return (response.data as QueueProfilesResponse) ?? { profiles: [] };
}

export async function fetchQrTokenInfo(token: string): Promise<QrTokenInfo> {
  const response = await api.get(`/queue/qr-tokens/${token}/info`);
  return response.data as QrTokenInfo;
}

export async function startQueueJoinSession(token: string): Promise<QueueJoinSessionData> {
  const response = await api.post('/queue/join/start', { token });
  return response.data as QueueJoinSessionData;
}

export async function completeQueueJoinSession(payload: Record<string, unknown>): Promise<QueueActionResponse> {
  const response = await api.post('/queue/join/complete', payload);
  return mapQueueActionResponseDto(response.data as Record<string, unknown>);
}

export async function fetchQueuesToday(targetDate: string): Promise<QueuePayload> {
  const response = await api.get('/registrar/queues/today', {
    params: withParams({ target_date: targetDate }),
  });
  return mapQueuePayloadDto(response.data as Record<string, unknown>);
}

export async function generateDoctorQrToken({
  specialistId,
  department,
  targetDate,
  expiresHours = 24,
}: {
  specialistId: string | number;
  department?: string;
  targetDate: string;
  expiresHours?: number;
}): Promise<QrData> {
  const payload = {
    specialist_id: Number(specialistId),
    department: department || 'general',
    target_date: targetDate,
    expires_hours: expiresHours,
  };
  const response = await api.post('/queue/admin/qr-tokens/generate', payload);
  return mapQrDataDto(response.data as Record<string, unknown>);
}

export async function generateClinicQrToken({
  targetDate,
  expiresHours = 24,
}: {
  targetDate: string;
  expiresHours?: number;
}): Promise<QrData> {
  const payload = {
    target_date: targetDate,
    expires_hours: expiresHours,
  };
  const response = await api.post(
    '/queue/admin/qr-tokens/generate-clinic',
    payload
  );
  return mapQrDataDto(response.data as Record<string, unknown>);
}

export async function openReceptionSlot({
  day,
  specialistId,
}: {
  day: string;
  specialistId: string | number;
}): Promise<QueueActionResponse> {
  const response = await api.post('/registrar/open-reception', null, {
    params: {
      day,
      specialist_id: specialistId,
    },
  });
  return mapQueueActionResponseDto(response.data as Record<string, unknown>);
}

// UX Audit Registrar #7: closeReceptionSlot — закрытие приёма.
// P2 ARCHITECTURE AUDIT: backend mounts this at /queue/legacy/close
// (queue.py is mounted with prefix="/queue/legacy" in api.py:389).
// The previous /queue/close path was a frontend orphan — no backend match.
export async function closeReceptionSlot({
  day,
  specialistId,
}: {
  day: string;
  specialistId: string | number;
}): Promise<QueueActionResponse> {
  const response = await api.post('/queue/legacy/close', null, {
    params: {
      day,
      specialist_id: specialistId,
    },
  });
  return mapQueueActionResponseDto(response.data as Record<string, unknown>);
}

export async function callNextQueuePatient({
  specialistId,
  targetDate,
}: {
  specialistId: string | number;
  targetDate: string;
}): Promise<QueueActionResponse> {
  const response = await api.post(
    `/queue/${Number(specialistId)}/call-next`,
    null,
    {
      params: withParams({ target_date: targetDate }),
    }
  );
  return mapQueueActionResponseDto(response.data as Record<string, unknown>);
}

/**
 * Массовое создание записей в очереди (при добавлении новых услуг)
 * @returns {Promise<QueueActionResponse>}
 */
export async function createQueueEntriesBatch({
  patientId,
  source,
  services,
}: {
  patientId: string | number;
  source: string;
  services: Array<{ specialist_id: string | number; service_id: string | number; quantity?: number }>;
}): Promise<QueueActionResponse> {
  const payload = {
    patient_id: Number(patientId),
    source,
    services: services.map((service) => ({
      specialist_id: Number(service.specialist_id),
      service_id: Number(service.service_id),
      quantity: Number(service.quantity || 1),
    })),
  };
  const response = await api.post(
    '/registrar-integration/queue/entries/batch',
    payload
  );
  return mapQueueActionResponseDto(response.data as Record<string, unknown>);
}

export async function applyRegistrarEditDelta({
  patientId,
  targetDate,
  patientData,
  services,
  paymentMethod = 'cash',
  discountMode = 'none',
  allFree = false,
  existingQueueEntryIds = [],
  // R-08 fix: optimistic locking — map of entry_id → ISO updated_at string.
  expectedEntryUpdatedAt = null,
}: {
  patientId: string | number;
  targetDate: string;
  patientData?: Record<string, unknown> | null;
  services: Array<{ service_id: string | number; quantity?: unknown; specialist_id?: string | number | null }>;
  paymentMethod?: string;
  discountMode?: string;
  allFree?: boolean;
  existingQueueEntryIds?: Array<string | number>;
  expectedEntryUpdatedAt?: Record<string, string> | null;
}): Promise<QueueActionResponse> {
  const payload: Record<string, unknown> = {
    patient_id: Number(patientId),
    target_date: targetDate,
    patient_data: patientData || null,
    payment_method: paymentMethod,
    discount_mode: discountMode,
    all_free: Boolean(allFree),
    services: (services || []).map((service) => ({
      service_id: Number(service.service_id),
      quantity: Number(service.quantity || 1),
      specialist_id: service.specialist_id === null || service.specialist_id === undefined
        ? null
        : Number(service.specialist_id),
    })),
    existing_queue_entry_ids: (existingQueueEntryIds || [])
      .filter((id) => id !== null && id !== undefined && id !== '')
      .map((id) => Number(id)),
  };
  // R-08 fix: add optimistic locking map if provided
  if (expectedEntryUpdatedAt && typeof expectedEntryUpdatedAt === 'object') {
    payload.expected_entry_updated_at = expectedEntryUpdatedAt;
  }
  const response = await api.post('/registrar/cart/edit-delta', payload);
  return mapQueueActionResponseDto(response.data as Record<string, unknown>);
}

/**
 * Обновление существующей QR-записи (вместо создания новой)
 * ⭐ SSOT: Этот endpoint обновляет существующую запись в очереди,
 * предотвращая создание дубликатов при редактировании QR-записей в мастере
 * @returns {Promise<QueueActionResponse>}
 */
export async function updateOnlineQueueEntry({
  entryId,
  patientData,
  visitType,
  discountMode,
  services,
  allFree = false,
  aggregatedIds = null,
}: {
  entryId: string | number;
  patientData: Record<string, unknown> | null;
  visitType: string;
  discountMode: string;
  services: Array<{ service_id: string | number; quantity?: unknown }>;
  allFree?: boolean;
  aggregatedIds?: Array<string | number> | null;
}): Promise<QueueActionResponse> {
  const payload = {
    patient_data: patientData,
    visit_type: visitType,
    discount_mode: discountMode,
    services: services.map((service) => ({
      service_id: Number(service.service_id),
      quantity: Number(service.quantity || 1),
    })),
    all_free: allFree,
    aggregated_ids: aggregatedIds,
  };
  const response = await api.put(
    `/queue/online-entry/${Number(entryId)}/full-update`,
    payload
  );
  return mapQueueActionResponseDto(response.data as Record<string, unknown>);
}

/** Helper for callers that need QueueData (not QueuePayload) directly. */
export async function fetchQueueDataForDoctor(
  targetDate: string,
  specialistId: string | number,
): Promise<QueueData | null> {
  const payload = await fetchQueuesToday(targetDate);
  if (!payload?.queues) return null;
  const id = Number(specialistId);
  return (
    payload.queues.find((q) => {
      const sid = q.specialist_id;
      return sid !== undefined && sid !== null && Number(sid) === id;
    }) ?? null
  );
}
