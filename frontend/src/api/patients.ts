// ADR-0016: WrappedApiError replaced by canonical HttpApiError from types/errors.ts.
import type { HttpApiError } from '../types/errors';

function createWrappedError(message: string, extras: { status?: number; detail?: string; code?: string; response?: unknown }): HttpApiError & Error {
  const err = new Error(message) as HttpApiError & Error;
  err.status = extras.status;
  err.detail = extras.detail;
  if (extras.code) err.code = extras.code;
  err.response = extras.response as HttpApiError['response'];
  return err;
}

/**
 * Fix A: backend returns structured details for domain errors, e.g.
 *   { code: 'patient_phone_exists', message: '...' }
 * Extract a machine-readable code + human message without guessing from
 * the status code or the text.
 */
function parseApiDetail(detail: unknown): { code?: string; message: string } {
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const d = detail as { code?: string; message?: string; error?: string };
    return {
      code: typeof d.code === 'string' ? d.code : undefined,
      message: d.message || d.error || 'Ошибка запроса',
    };
  }
  if (typeof detail === 'string' && detail) return { message: detail };
  return { message: 'Ошибка запроса' };
}

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
import type { PatientDto } from '../types/api';
import type { Patient } from '../types/domain/clinic';
import { mapPatientDto, mapPatientDtos } from './mappers';

// =====================================================================
// PATIENTS API
// =====================================================================

/**
 * Получить пациента по ID.
 * @returns {Promise<Patient>} Domain Patient (canonical)
 * @throws {Error} Если пациент не найден или сеть недоступна
 */
export async function getPatient(patientId: string | number): Promise<Patient> {
  const response = await api.get<PatientDto>(`/patients/${patientId}`);
  return mapPatientDto(response.data);
}

/**
 * Создать нового пациента.
 * @param patientData - { full_name, phone, sex, last_name, first_name, ... }
 * @returns {Promise<Patient>} Created patient (domain)
 * @throws {Error} Если валидация не прошла (например, телефон уже существует)
 */
export async function createPatient(patientData: Record<string, unknown>): Promise<Patient> {
  try {
    const response = await api.post<PatientDto>('/patients/', patientData);
    return mapPatientDto(response.data);
  } catch (error) {
    // Fix A: machine-readable code from the structured detail (if present);
    // no invented "patient exists" message for arbitrary 400s.
    const status = (error as HttpApiError)?.response?.status;
    const { code, message } = parseApiDetail((error as HttpApiError)?.response?.data?.detail);
    if (status === 400) {
      throw createWrappedError(message, { status: 400, detail: message, code, response: (error as HttpApiError)?.response });
    }
    throw createWrappedError(message || 'Ошибка создания пациента', { status: status as number | undefined, code, response: (error as HttpApiError)?.response });
  }
}

/**
 * Обновить пациента (PUT /patients/{id}).
 * @returns {Promise<Patient>} Updated patient (domain)
 */
export async function updatePatient(patientId: string | number, updateData: Record<string, unknown>): Promise<Patient> {
  try {
    const response = await api.put<PatientDto>(`/patients/${patientId}`, updateData);
    return mapPatientDto(response.data);
  } catch (error) {
    const status = (error as HttpApiError)?.response?.status;
    const { code, message } = parseApiDetail((error as HttpApiError)?.response?.data?.detail);
    logger.error('[patients API] updatePatient failed', { patientId, status, code, detail: message });
    throw createWrappedError(message || `Ошибка обновления пациента (${status || 'network'})`, { status: status as number | undefined, code, response: (error as HttpApiError)?.response });
  }
}

/**
 * Найти пациентов по телефону.
 * @returns {Promise<Patient[]>} Массив найденных пациентов (домен)
 */
export async function searchPatientsByPhone(phone: string): Promise<Patient[]> {
  if (!phone) return [];
  const response = await api.get<unknown>('/patients/', {
    params: { phone },
  });
  return mapPatientDtos(response.data);
}

/**
 * Найти пациентов по произвольному запросу (ФИО, телефон, ID).
 * @param query - Минимум 2 символа
 * @returns {Promise<Patient[]>} Массив найденных пациентов (домен)
 */
export async function searchPatients(query: string): Promise<Patient[]> {
  if (!query || query.length < 2) return [];
  const response = await api.get<unknown>('/patients/', {
    params: { q: query },
  });
  return mapPatientDtos(response.data);
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
export async function checkAuthProbe(): Promise<boolean> {
  try {
    await api.get('/patients/', { params: { _limit: 1 } });
    return true;
  } catch (error) {
    const status = (error as HttpApiError)?.response?.status;
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
 * @api-transport backend returns a free-form cart result dict that varies
 *               by visit_type / discount_mode combination; no domain type
 *               exists yet (planned for Wave 4 follow-up when the wizard
 *               cart refactor lands).
 *
 * @param cartData - { patient_id, visits, discount_mode, payment_method, all_free, notes }
 * @returns {Promise<Record<string, unknown>>} Created cart result
 */
export async function createRegistrarCart(cartData: Record<string, unknown>): Promise<Record<string, unknown>> {
  try {
    const response = await api.post('/registrar/cart', cartData);
    return response.data;
  } catch (error) {
    const status = (error as HttpApiError)?.response?.status;
    const detail = (error as HttpApiError)?.response?.data?.detail;
    logger.error('[patients API] createRegistrarCart failed', { status, detail });
    throw createWrappedError(String(detail || `Ошибка создания записи (${status || 'network'})`), { status: status as number | undefined, response: (error as HttpApiError)?.response });
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
export async function findPatientByPhoneVariants(phone: string): Promise<Patient | null> {
  if (!phone) return null;

  // Очищенный телефон (только цифры, без + и пробелов)
  const digits = String(phone).replace(/\D/g, '');

  // Попытка 1: Поиск по форматированному номеру
  let patients = await searchPatientsByPhone(phone);
  let found = patients.find((p) => String(p.phone || '').replace(/\D/g, '') === digits);
  if (found) return found;

  // Попытка 2: Поиск по очищенному номеру (если отличается от форматированного)
  if (digits.length >= 9 && digits !== phone) {
    patients = await searchPatientsByPhone(digits);
    found = patients.find((p) => String(p.phone || '').replace(/\D/g, '') === digits);
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
