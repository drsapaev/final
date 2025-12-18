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
 * Получить user_id по doctor_id
 * @param {number} doctorId - ID врача (doctor_id)
 * @returns {Promise<number>} user_id
 */
export async function getDoctorUserId(doctorId) {
  const response = await api.get(
    `/registrar-integration/doctors/${Number(doctorId)}/user-id`
  );
  return response.data.user_id;
}

/**
 * Массовое создание записей в очереди (при добавлении новых услуг)
 * @param {Object} params - Параметры для создания очередей
 * @param {number} params.patientId - ID пациента
 * @param {string} params.source - Источник регистрации: 'online', 'desk', 'morning_assignment'
 * @param {Array<{specialist_id: number, service_id: number, quantity: number}>} params.services - Список услуг
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
