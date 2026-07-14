import { api } from './client';

const withParams = (params) =>
  Object.fromEntries(
    Object.entries(params || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );

export async function fetchAvailableSpecialists() {
  const response = await api.get('/queue/available-specialists');
  const payload = response.data?.specialists ?? response.data ?? [];
  return Array.isArray(payload) ? payload : [];
}

export async function fetchPublicQueueProfiles() {
  const response = await api.get('/queues/profiles/public');
  return response.data;
}

export async function fetchQrTokenInfo(token) {
  const response = await api.get(`/queue/qr-tokens/${token}/info`);
  return response.data;
}

export async function startQueueJoinSession(token) {
  const response = await api.post('/queue/join/start', { token });
  return response.data;
}

export async function completeQueueJoinSession(payload) {
  const response = await api.post('/queue/join/complete', payload);
  return response.data;
}

export async function fetchQueuesToday(targetDate) {
  const response = await api.get('/registrar/queues/today', {
    params: withParams({ target_date: targetDate }),
  });
  return response.data;
}

export async function generateDoctorQrToken({
  specialistId,
  department,
  targetDate,
  expiresHours = 24,
}) {
  const payload = {
    specialist_id: Number(specialistId),
    department: department || 'general',
    target_date: targetDate,
    expires_hours: expiresHours,
  };
  const response = await api.post('/queue/admin/qr-tokens/generate', payload);
  return response.data;
}

export async function generateClinicQrToken({
  targetDate,
  expiresHours = 24,
}) {
  const payload = {
    target_date: targetDate,
    expires_hours: expiresHours,
  };
  const response = await api.post(
    '/queue/admin/qr-tokens/generate-clinic',
    payload
  );
  return response.data;
}

export async function openReceptionSlot({ day, specialistId }) {
  const response = await api.post('/registrar/open-reception', null, {
    params: {
      day,
      specialist_id: specialistId,
    },
  });
  return response.data;
}

// UX Audit Registrar #7: closeReceptionSlot — закрытие приёма.
// P2 ARCHITECTURE AUDIT: backend mounts this at /queue/legacy/close
// (queue.py is mounted with prefix="/queue/legacy" in api.py:389).
// The previous /queue/close path was a frontend orphan — no backend match.
export async function closeReceptionSlot({ day, specialistId }) {
  const response = await api.post('/queue/legacy/close', null, {
    params: {
      day,
      specialist_id: specialistId,
    },
  });
  return response.data;
}

export async function callNextQueuePatient({ specialistId, targetDate }) {
  const response = await api.post(
    `/queue/${Number(specialistId)}/call-next`,
    null,
    {
      params: withParams({ target_date: targetDate }),
    }
  );
  return response.data;
}

/**
 * Массовое создание записей в очереди (при добавлении новых услуг)
 * @param {Object} params - Параметры для создания очередей
 * @param {number} params.patientId - ID пациента
 * @param {string} params.source - Источник регистрации: 'online', 'desk', 'morning_assignment'
 * @param {Array<{specialist_id: number, service_id: number, quantity: number}>} params.services - Список услуг, где specialist_id = Doctor.id
 * @returns {Promise<{success: boolean, entries: Array, message: string}>}
 */
export async function createQueueEntriesBatch({ patientId, source, services }) {
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
  return response.data;
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
  // Если передан, backend проверит что ни одна entry не была изменена
  // другим пользователем с момента последнего чтения.
  expectedEntryUpdatedAt = null,
}) {
  const payload = {
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
  return response.data;
}

/**
 * Обновление существующей QR-записи (вместо создания новой)
 * ⭐ SSOT: Этот endpoint обновляет существующую запись в очереди,
 * предотвращая создание дубликатов при редактировании QR-записей в мастере
 * 
 * @param {Object} params - Параметры для обновления
 * @param {number} params.entryId - ID записи в очереди (queue_entry.id)
 * @param {Object} params.patientData - Данные пациента {patient_name, phone, birth_year, address}
 * @param {string} params.visitType - Тип визита: 'paid', 'repeat', 'benefit'
 * @param {string} params.discountMode - Режим скидки: 'none', 'repeat', 'benefit', 'all_free'
 * @param {Array<{service_id: number, quantity: number}>} params.services - Список услуг
 * @param {boolean} params.allFree - Все услуги бесплатны
 * @returns {Promise<{success: boolean, entry: Object, total_amount: number}>}
 */
export async function updateOnlineQueueEntry({
  entryId,
  patientData,
  visitType,
  discountMode,
  services,
  allFree = false,
  aggregatedIds = null,  // ⭐ FIX: IDs of all merged entries for dedup check
}) {
  const payload = {
    patient_data: patientData,
    visit_type: visitType,
    discount_mode: discountMode,
    services: services.map((service) => ({
      service_id: Number(service.service_id),
      quantity: Number(service.quantity || 1),
    })),
    all_free: allFree,
    aggregated_ids: aggregatedIds,  // ⭐ FIX: Pass to backend for dedup
  };
  const response = await api.put(
    `/queue/online-entry/${Number(entryId)}/full-update`,
    payload
  );
  return response.data;
}
