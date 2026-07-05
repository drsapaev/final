/**
 * Patients API client — centralized wrapper over `api` from api/client.js.
 *
 * UX Audit Stage 3 (Wizard issue 5.1):
 * Раньше в AppointmentWizardV2.jsx было 13 raw fetch() вызовов к /patients/*
 * и /registrar/cart с дублированием:
 *   - URL-построения (`${API_BASE}/patients/?phone=...`)
 *   - Headers (Authorization, Content-Type)
 *   - JSON-parsing и error-handling
 *
 * Этот модуль инкапсулирует все patients/cart операции в одном месте.
 * Auth/CSRF/refresh-token обрабатываются централизованно через axios-interceptor
 * в api/client.js — здесь мы этим не занимаемся.
 *
 * Все методы возвращают Promise<data> (response.data) и бросают Error
 * с человекочитаемым сообщением при неудаче.
 */

import { api } from './client';
import logger from '../utils/logger';

// =====================================================================
// PATIENTS API
// =====================================================================

/**
 * Получить пациента по ID.
 * @param {number|string} patientId
 * @returns {Promise<object>} Patient object
 * @throws {Error} Если пациент не найден или сеть недоступна
 */
export async function getPatient(patientId) {
  const response = await api.get(`/patients/${patientId}`);
  return response.data;
}

/**
 * Создать нового пациента.
 * @param {object} patientData - { full_name, phone, sex, last_name, first_name, ... }
 * @returns {Promise<object>} Created patient with id
 * @throws {Error} Если валидация не прошла (например, телефон уже существует)
 */
export async function createPatient(patientData) {
  try {
    const response = await api.post('/patients/', patientData);
    return response.data;
  } catch (error) {
    // 400 — типичная ошибка «пациент уже существует»
    if (error?.response?.status === 400) {
      const detail = error?.response?.data?.detail || 'Пациент с таким номером телефона уже существует';
      const wrapped = new Error(detail);
      wrapped.status = 400;
      wrapped.detail = detail;
      wrapped.response = error.response;
      throw wrapped;
    }
    // Другие ошибки — пробрасываем с нормализованным сообщением
    const message = error?.response?.data?.detail || error?.message || 'Ошибка создания пациента';
    const wrapped = new Error(message);
    wrapped.status = error?.response?.status;
    wrapped.response = error?.response;
    throw wrapped;
  }
}

/**
 * Обновить пациента (PUT /patients/{id}).
 * @param {number|string} patientId
 * @param {object} updateData - Частичные данные для обновления
 * @returns {Promise<object>} Updated patient
 */
export async function updatePatient(patientId, updateData) {
  try {
    const response = await api.put(`/patients/${patientId}`, updateData);
    return response.data;
  } catch (error) {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail;
    logger.error('[patients API] updatePatient failed', { patientId, status, detail });
    const wrapped = new Error(detail || `Ошибка обновления пациента (${status || 'network'})`);
    wrapped.status = status;
    wrapped.response = error?.response;
    throw wrapped;
  }
}

/**
 * Найти пациентов по телефону.
 * @param {string} phone - Телефон в любом формате (+998XXXXXXXXX, XXXXXXXXX)
 * @returns {Promise<Array<object>>} Массив найденных пациентов (может быть пустым)
 */
export async function searchPatientsByPhone(phone) {
  if (!phone) return [];
  const response = await api.get('/patients/', {
    params: { phone },
  });
  return response.data;
}

/**
 * Найти пациентов по произвольному запросу (ФИО, телефон, ID).
 * @param {string} query - Минимум 2 символа
 * @returns {Promise<Array<object>>} Массив найденных пациентов
 */
export async function searchPatients(query) {
  if (!query || query.length < 2) return [];
  const response = await api.get('/patients/', {
    params: { q: query },
  });
  return response.data;
}

/**
 * Проверить, авторизован ли пользователь (lightweight probe через GET /patients/).
 *
 * UX Audit: Раньше Wizard делал «test fetch» к /patients/ перед submit,
 * чтобы проверить токен. Теперь это делается через api-клиент — если
 * interceptor вернёт 401, мы это знаем. Метод оставлен для backward-compat.
 *
 * @returns {Promise<boolean>} true если авторизован
 */
export async function checkAuthProbe() {
  try {
    await api.get('/patients/', { params: { _limit: 1 } });
    return true;
  } catch (error) {
    const status = error?.response?.status;
    if (status === 401 || status === 403) {
      return false;
    }
    // Сетевые ошибки — не делаем вывод, что не авторизован
    logger.warn('[patients API] checkAuthProbe network error', { status });
    return true;
  }
}

// =====================================================================
// REGISTRAR CART API
// =====================================================================

/**
 * Создать корзину визитов (POST /registrar/cart).
 *
 * @param {object} cartData - { patient_id, visits, discount_mode, payment_method, all_free, notes }
 * @returns {Promise<object>} Created cart result
 */
export async function createRegistrarCart(cartData) {
  try {
    const response = await api.post('/registrar/cart', cartData);
    return response.data;
  } catch (error) {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail;
    logger.error('[patients API] createRegistrarCart failed', { status, detail });
    const wrapped = new Error(detail || `Ошибка создания записи (${status || 'network'})`);
    wrapped.status = status;
    wrapped.response = error?.response;
    throw wrapped;
  }
}

// =====================================================================
// HIGH-LEVEL HELPER: findOrCreatePatientByPhone
// =====================================================================

/**
 * UX Audit Stage 3 (Wizard issue 5.3):
 * Унификация дублированной логики поиска пациента по телефону.
 *
 * Раньше в Wizard было 4 места с почти идентичным кодом:
 *   1. handlePhoneBlur (строка ~556)
 *   2. handleComplete edit-mode (строка ~1631)
 *   3. handleComplete create-mode fallback (строка ~1816)
 *   4. handleComplete edit-mode QR fallback (строка ~1649)
 *
 * Все искали пациента по двум вариантам телефона: форматированному (+998...) и
 * очищенному (998XXX...). Этот helper инкапсулирует оба варианта.
 *
 * @param {string} phone - Телефон в любом формате
 * @returns {Promise<object|null>} Найденный пациент или null
 */
export async function findPatientByPhoneVariants(phone) {
  if (!phone) return null;

  // Очищенный телефон (только цифры, без + и пробелов)
  const digits = String(phone).replace(/\D/g, '');

  // Попытка 1: Поиск по форматированному номеру
  let patients = await searchPatientsByPhone(phone);
  let found = patients.find((p) => (p.phone || '').replace(/\D/g, '') === digits);
  if (found) return found;

  // Попытка 2: Поиск по очищенному номеру (если отличается от форматированного)
  if (digits.length >= 9 && digits !== phone) {
    patients = await searchPatientsByPhone(digits);
    found = patients.find((p) => (p.phone || '').replace(/\D/g, '') === digits);
    if (found) return found;
  }

  return null;
}

const patientsAPI = {
  get: getPatient,
  create: createPatient,
  update: updatePatient,
  searchByPhone: searchPatientsByPhone,
  search: searchPatients,
  checkAuth: checkAuthProbe,
  createCart: createRegistrarCart,
  findByPhoneVariants: findPatientByPhoneVariants,
};

export default patientsAPI;
