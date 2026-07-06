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
 * Каждый из них дублировал:
 *   - URL-построение (`${API_BASE}/registrar/price-overrides?...`)
 *   - Headers (Authorization, Content-Type)
 *   - JSON-parsing и error-handling
 *
 * Этот модуль инкапсулирует все registrar-операции в одном месте.
 * Auth/CSRF/refresh-token обрабатываются централизованно через
 * axios-interceptor в api/client.js — здесь мы этим не занимаемся.
 *
 * Все методы возвращают Promise<data> (response.data) и бросают Error
 * с человекочитаемым сообщением при неудаче.
 */

import { api } from './client';
import logger from '../utils/logger';

// =====================================================================
// PRICE OVERRIDE (одобрение/отклонение изменений цен врачами)
// =====================================================================

/**
 * Загрузить список изменений цен.
 * @param {Object} [options]
 * @param {string} [options.statusFilter='pending'] - pending | approved | rejected | all
 * @param {number} [options.limit=100]
 * @returns {Promise<Array<object>>} Массив overrides
 */
export async function fetchPriceOverrides({ statusFilter = 'pending', limit = 100 } = {}) {
  const response = await api.get('/registrar/price-overrides', {
    params: { status_filter: statusFilter, limit },
  });
  // Backend может вернуть как массив, так и объект с пагинацией.
  const data = response.data;
  return Array.isArray(data) ? data : data?.items ?? data?.overrides ?? [];
}

/**
 * Одобрить или отклонить изменение цены.
 * @param {Object} params
 * @param {number|string} params.overrideId
 * @param {'approve'|'reject'} params.action
 * @param {string} [params.rejectionReason] - обязательно при action === 'reject'
 * @returns {Promise<{message: string}>} Сообщение от backend
 */
export async function approvePriceOverride({ overrideId, action, rejectionReason = null }) {
  const response = await api.post('/registrar/price-override/approve', {
    override_id: overrideId,
    action,
    rejection_reason: rejectionReason,
  });
  return response.data;
}

// =====================================================================
// DOCTORS & QUEUE SETTINGS (для IntegratedDoctorSelector)
// =====================================================================

/**
 * Загрузить список врачей регистратуры с их расписаниями.
 * @returns {Promise<{doctors: Array<object>}>}
 */
export async function fetchRegistrarDoctors() {
  const response = await api.get('/registrar/doctors');
  return response.data;
}

/**
 * Загрузить настройки очередей (по специальностям).
 * @returns {Promise<object>} Например: { specialties: { cardiology: { start_number, max_per_day } } }
 */
export async function fetchRegistrarQueueSettings() {
  const response = await api.get('/registrar/queue-settings');
  return response.data;
}

// =====================================================================
// SERVICES (для IntegratedServiceSelector)
// =====================================================================

/**
 * Загрузить справочник услуг регистратуры, сгруппированный по specialty/group.
 * @returns {Promise<{services_by_group: object, categories?: Array<object>}>}
 */
export async function fetchRegistrarServices() {
  const response = await api.get('/registrar/services');
  return response.data;
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
