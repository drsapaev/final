/**
 * Registrar API client — centralized wrapper over `api` from api/client.js.
 *
 * UX Audit Registrar Stage #1 (registrar api migration):
 * Раньше 4 файла использовали raw fetch() к registrar-эндпоинтам:
 *   - components/registrar/PriceOverrideApproval.jsx (2 вызова)
 *   - components/registrar/IntegratedDoctorSelector.jsx (2 вызова)
 *   - components/registrar/IntegratedServiceSelector.jsx (1 вызов)
 *   - pages/RegistrarPanel.jsx (1 вызов: loadPatientFromUrl)
 *
 * Этот модуль инкапсулирует все registrar-операции в одном месте.
 * Auth/CSRF/refresh-token обрабатываются централизованно через
 * axios-interceptor в api/client.js — здесь мы этим не занимаемся.
 *
 * Wave 4: most functions still return `Record<string, unknown>` because
 * the registrar endpoints return backend-specific dicts (price-override
 * queues, queue settings, services-by-group) that don't map cleanly to
 * the canonical domain types. The doctor list is mapped to `Doctor[]`
 * via mapDoctorDtos; other endpoints will gain dedicated domain types
 * in a future wave once the UI consumers are refactored to read typed
 * fields instead of treating the response as a free-form bag.
 */

import { api } from './client';
import logger from '../utils/logger';
import type { Doctor } from '../types/domain/clinic';
import { mapDoctorDtos } from './mappers';

// =====================================================================
// PRICE OVERRIDE (одобрение/отклонение изменений цен врачами)
// =====================================================================

/**
 * Price override entry in the registrar approval queue.
 * Returned by GET /registrar/price-overrides.
 */
export interface PriceOverrideEntry {
  id: string | number;
  status?: 'pending' | 'approved' | 'rejected' | string;
  service_id?: string | number;
  service_name?: string;
  doctor_id?: string | number;
  doctor_name?: string;
  patient_name?: string;
  original_price?: number;
  requested_price?: number;
  new_price?: number;
  reason?: string;
  details?: string;
  created_at?: string;
  [key: string]: unknown;
}

/**
 * Response from approve/reject endpoint.
 */
export interface PriceOverrideActionResponse {
  message: string;
  override_id?: string | number;
  status?: string;
  [key: string]: unknown;
}

/**
 * Загрузить список изменений цен.
 * @param options.statusFilter - pending | approved | rejected | all
 * @param options.limit
 * @returns {Promise<PriceOverrideEntry[]>} Массив overrides (домен)
 */
export async function fetchPriceOverrides({
  statusFilter = 'pending',
  limit = 100,
}: {
  statusFilter?: string;
  limit?: number;
} = {}): Promise<PriceOverrideEntry[]> {
  const response = await api.get('/registrar/price-overrides', {
    params: { status_filter: statusFilter, limit },
  });
  // Backend может вернуть как массив, так и объект с пагинацией.
  const data = response.data;
  const items: unknown = Array.isArray(data) ? data : (data as { items?: unknown; overrides?: unknown })?.items ?? (data as { overrides?: unknown })?.overrides ?? [];
  return (Array.isArray(items) ? items : []).map((item) => item as PriceOverrideEntry);
}

/**
 * Одобрить или отклонить изменение цены.
 * @returns {Promise<PriceOverrideActionResponse>} Сообщение от backend
 */
export async function approvePriceOverride({
  overrideId,
  action,
  rejectionReason = null,
}: {
  overrideId: string | number;
  action: 'approve' | 'reject';
  rejectionReason?: string | null;
}): Promise<PriceOverrideActionResponse> {
  const response = await api.post('/registrar/price-override/approve', {
    override_id: overrideId,
    action,
    rejection_reason: rejectionReason,
  });
  return response.data as PriceOverrideActionResponse;
}

// =====================================================================
// DOCTORS & QUEUE SETTINGS (для IntegratedDoctorSelector)
// =====================================================================

/**
 * Response shape from GET /registrar/doctors.
 * Backend returns `{ doctors: DoctorRow[] }`; we keep the envelope so
 * consumers that read `result.doctors` keep working. The Doctor rows
 * inside are mapped to the canonical domain Doctor type.
 */
export interface RegistrarDoctorsResponse {
  doctors: Doctor[];
  [key: string]: unknown;
}

/**
 * Загрузить список врачей регистратуры с их расписаниями.
 * @returns {Promise<RegistrarDoctorsResponse>} Объект с массивом врачей (домен)
 */
export async function fetchRegistrarDoctors(): Promise<RegistrarDoctorsResponse> {
  const response = await api.get('/registrar/doctors');
  const data = response.data;
  // Backend returns { doctors: [...] }. Map each row to domain Doctor.
  const list: unknown = Array.isArray(data) ? data : (data as { doctors?: unknown })?.doctors ?? [];
  const doctors = mapDoctorDtos(list);
  return { doctors, ...(data as Record<string, unknown> ?? {}) };
}

/**
 * Queue settings per specialty.
 * Returned by GET /registrar/queue-settings.
 * Free-form dict — backend-owned, not yet normalized to a domain type.
 */
export interface QueueSettings {
  specialties?: Record<string, {
    start_number?: number;
    max_per_day?: number;
    auto_close_time?: string;
    [key: string]: unknown;
  }>;
  [key: string]: unknown;
}

/**
 * Загрузить настройки очередей (по специальностям).
 * @returns {Promise<QueueSettings>}
 */
export async function fetchRegistrarQueueSettings(): Promise<QueueSettings> {
  const response = await api.get('/registrar/queue-settings');
  return response.data as QueueSettings;
}

// =====================================================================
// SERVICES (для IntegratedServiceSelector)
// =====================================================================

/**
 * Services catalog grouped by specialty/group.
 * Returned by GET /registrar/services.
 * Free-form dict — backend-owned, not yet normalized to a domain type.
 */
export interface RegistrarServicesResponse {
  services_by_group?: Record<string, unknown>;
  categories?: unknown[];
  [key: string]: unknown;
}

/**
 * Загрузить справочник услуг регистратуры, сгруппированный по specialty/group.
 * @returns {Promise<RegistrarServicesResponse>}
 */
export async function fetchRegistrarServices(): Promise<RegistrarServicesResponse> {
  const response = await api.get('/registrar/services');
  return response.data as RegistrarServicesResponse;
}

// =====================================================================
// DEFAULT EXPORT (для backward-compat и удобства)
// =====================================================================

const registrarAPI = {
  fetchPriceOverrides,
  approvePriceOverride,
  fetchRegistrarDoctors,
  fetchRegistrarQueueSettings,
  fetchRegistrarServices,
};

export default registrarAPI;

// Логируем инициализацию модуля (один раз, для отладки).
logger.debug('[api/registrar] module initialized');
