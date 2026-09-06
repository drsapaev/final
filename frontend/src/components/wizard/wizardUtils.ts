/**
 * UX Audit Stage 3 (Wizard issue 5.2):
 * Вынесенные helper-функции и константы из AppointmentWizardV2.jsx.
 *
 * Раньше основной файл wizard'а содержал 4175 строк, из которых ~280 строк
 * были utility-функциями для нормализации данных, queue-управления и т.д.
 * Теперь они в этом модуле, что:
 *   - Уменьшает основной файл
 *   - Позволяет переиспользовать функции в тестах
 *   - Упрощает code review (утилиты отделены от UI-логики)
 */

import { toast } from 'react-toastify';
import { normalizeCategoryCode } from '../../utils/serviceCodeUtils';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import { ClipboardList, FlaskConical, Stethoscope, Syringe } from 'lucide-react';

// =====================================================================
// CONSTANTS
// =====================================================================

export const PATIENT_NAME_PATTERN = /^[\p{L}\s\-']+$/u;
export const MIXED_REPEAT_WARNING =
  'В текущей модели repeat применяется на весь checkout; для точного применения разделите оформление по специалистам.';

// Именованные константы шагов wizard'а вместо магических чисел 1/2.
export const STEP_PATIENT = 1;
export const STEP_CART = 2;
export const TOTAL_STEPS = 2;

// =====================================================================
// DATE HELPERS
// =====================================================================

export const getLocalISODate = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// =====================================================================
// CONTRACT / NORMALIZATION HELPERS
// =====================================================================

export const normalizeWizardContractValue = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  return String(value).trim().toLowerCase();
};

export const getWizardRecordKind = (record: Record<string, unknown> | null | undefined): string =>
  normalizeWizardContractValue(record?.record_kind ?? record?.record_type ?? record?.type);

export const getWizardSourceKind = (record: Record<string, unknown> | null | undefined): string =>
  normalizeWizardContractValue(record?.source_kind ?? record?.source);

export const hasQueueIdentityValue = (value: unknown): boolean =>
  value !== null && value !== undefined && value !== '';

// =====================================================================
// QUEUE ENTRY ID RESOLUTION
// =====================================================================

interface QueueRecordLike {
  original_queue_id?: unknown;
  queue_entry_id?: unknown;
  doctor_queue_entry_id?: unknown;
  queue_id?: unknown;
  id?: unknown;
  queue_numbers?: unknown;
  record_kind?: unknown;
  record_type?: unknown;
  type?: unknown;
  source_kind?: unknown;
  source?: unknown;
  [key: string]: unknown;
}

export const resolveExplicitQueueEntryId = (
  record: QueueRecordLike | null | undefined,
  { allowLegacyId = true }: { allowLegacyId?: boolean } = {}
): string | number | null => {
  if (!record || typeof record !== 'object') return null;

  const explicitQueueEntryId =
    record.original_queue_id ?? record.queue_entry_id ?? record.doctor_queue_entry_id ?? null;
  if (hasQueueIdentityValue(explicitQueueEntryId)) {
    return (explicitQueueEntryId as string | number) ?? null;
  }

  if (!allowLegacyId || hasQueueIdentityValue(record.queue_id)) {
    return null;
  }

  return hasQueueIdentityValue(record.id) ? ((record.id as string | number) ?? null) : null;
};

export const getFirstQueueNumberId = (record: QueueRecordLike | null | undefined): string | number | null => {
  if (!Array.isArray(record?.queue_numbers) || record.queue_numbers.length === 0) {
    return null;
  }
  return resolveExplicitQueueEntryId(record.queue_numbers[0] as QueueRecordLike);
};

export const resolveOnlineQueueEntryId = (
  record: QueueRecordLike | null | undefined,
  recordKind: string,
  effectiveSource: string
): string | number | null => {
  if (!record || recordKind !== 'online_queue' || effectiveSource !== 'online') {
    return null;
  }
  return resolveExplicitQueueEntryId(record) ?? getFirstQueueNumberId(record);
};

// =====================================================================
// QUEUE CANCELLATION (when cart items removed)
// =====================================================================

interface CartItemLike {
  original_queue_id?: string | number | null;
  [key: string]: unknown;
}

export const getRemovedQueueEntryIds = (
  originalQueueIds: Array<string | number> | null | undefined,
  cartItems: CartItemLike[] = []
): Array<string | number> => {
  const currentQueueIds = new Set<string | number>(
    cartItems
      .map((item) => item.original_queue_id)
      .filter((id): id is string | number => Boolean(id))
  );

  return Array.from(originalQueueIds || []).filter((id) => !currentQueueIds.has(id));
};

export const cancelRemovedQueueEntries = async (
  originalQueueIds: Array<string | number> | null | undefined,
  cartItems: CartItemLike[],
  contextLabel: string
): Promise<void> => {
  const removedQueueIds = getRemovedQueueEntryIds(originalQueueIds, cartItems);
  if (removedQueueIds.length === 0) {
    logger.log(`[AppointmentWizardV2] no removed queue entries to cancel (${contextLabel})`);
    return;
  }

  logger.log(
    `[AppointmentWizardV2] cancelling removed queue entries (${contextLabel}): ${removedQueueIds.join(', ')}`
  );
  const results = await Promise.allSettled(
    removedQueueIds.map((id) => api.post(`/online-queue/entries/${id}/cancel`))
  );
  const failedIds = results
    .map((result, index) => ({ result, id: removedQueueIds[index] }))
    .filter(({ result }) => result.status === 'rejected')
    .map(({ id }) => id as string | number);

  if (failedIds.length > 0) {
    logger.error('[AppointmentWizardV2] failed to cancel removed queue entries', {
      contextLabel,
      failedIds,
    });
    toast.warning('Не удалось отменить часть удаленных записей очереди. Обновите очередь.');
    return;
  }

  logger.log(`[AppointmentWizardV2] removed queue entries cancelled (${contextLabel})`);
};

// =====================================================================
// SERVICE SELECTION NORMALIZATION
// =====================================================================

type ServiceSelectionValue = string | number | bigint | Record<string, unknown> | null | undefined;

export const normalizeServiceSelectionValue = (serviceValue: ServiceSelectionValue): string => {
  if (serviceValue == null) return '';

  if (
    typeof serviceValue === 'string' ||
    typeof serviceValue === 'number' ||
    typeof serviceValue === 'bigint'
  ) {
    return String(serviceValue).trim();
  }

  if (typeof serviceValue === 'object') {
    const obj = serviceValue as Record<string, unknown>;
    const candidate =
      obj.service_code ||
      obj.code ||
      obj.name ||
      obj.label ||
      obj.title ||
      obj.service_name ||
      obj.value ||
      obj._temp_name ||
      '';
    return String(candidate).trim();
  }

  return String(serviceValue).trim();
};

export const normalizeServiceSelectionName = (serviceValue: ServiceSelectionValue): string => {
  if (serviceValue == null) return '';

  if (typeof serviceValue === 'object') {
    const obj = serviceValue as Record<string, unknown>;
    const candidate =
      obj.name ||
      obj.service_name ||
      obj.label ||
      obj.title ||
      obj.code ||
      obj.service_code ||
      obj.value ||
      '';
    return String(candidate).trim();
  }

  return String(serviceValue).trim();
};

// =====================================================================
// GENDER / SEX NORMALIZATION
// =====================================================================

export const normalizeGenderForForm = (value: unknown): string => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '';
  if (['m', 'male', 'man', 'men', '1', 'м', 'муж', 'мужской', 'мужчина', 'erkak'].includes(normalized))
    return 'male';
  if (['f', 'female', 'woman', 'women', '2', 'ж', 'жен', 'женский', 'женщина', 'ayol'].includes(normalized))
    return 'female';
  return String(value);
};

export const firstNonEmpty = (...values: Array<unknown>): unknown => {
  for (const value of values) {
    if (value !== null && value !== undefined && String(value).trim() !== '') {
      return value;
    }
  }
  return '';
};

interface PatientGenderRecordLike {
  patient_gender?: unknown;
  patient_sex?: unknown;
  gender?: unknown;
  sex?: unknown;
  patient?: { gender?: unknown; sex?: unknown } | null;
}

export const resolvePatientGenderValue = (record: PatientGenderRecordLike | null | undefined): unknown =>
  firstNonEmpty(
    record?.patient_gender,
    record?.patient_sex,
    record?.gender,
    record?.sex,
    record?.patient?.gender,
    record?.patient?.sex
  );

export const genderToPatientSexForApi = (value: unknown): 'M' | 'F' | null => {
  const normalized = normalizeGenderForForm(value);
  if (normalized === 'male') return 'M';
  if (normalized === 'female') return 'F';
  return null;
};

// =====================================================================
// CART QUOTE (Fix D: server-side pricing preview)
// =====================================================================

export interface CartQuoteItem {
  service_id: number;
  service_name: string;
  unit_price: number;
  quantity: number;
  discount_percent: number;
  final_price: number;
}

export interface CartQuote {
  items: CartQuoteItem[];
  total_amount: number;
  approval_status: string; // "approved" | "pending"
}

export type CartQuoteStatus = 'idle' | 'loading' | 'ready' | 'error';

interface QuoteCartSource {
  items?: Array<{ service_id?: unknown; quantity?: unknown }>;
  discount_mode?: unknown;
  all_free?: unknown;
}

// Строит запрос квоты из корзины. null — когда нет ни одной позиции
// с разрешённым service_id (квотировать нечего).
export const buildCartQuoteRequest = (
  cart: QuoteCartSource | null | undefined
): { items: Array<{ service_id: number; quantity: number }>; discount_mode: string; all_free: boolean } | null => {
  const rawItems = Array.isArray(cart?.items) ? cart.items : [];
  const items = rawItems
    .filter((item) => item && item.service_id != null)
    .map((item) => ({
      service_id: Number(item.service_id),
      quantity: Math.max(1, Number(item.quantity || 1)),
    }));
  if (items.length === 0) return null;
  return {
    items,
    discount_mode: String(cart?.discount_mode || 'none'),
    all_free: Boolean(cart?.all_free),
  };
};

// =====================================================================
// BIRTH DATE INPUT MASK (extracted from AppointmentWizardV2)
// =====================================================================

// Маска ввода: только цифры, максимум 8, формат ДД.ММ.ГГГГ
export const formatBirthDateInput = (value: string): string => {
  const digits = value.replace(/\D/g, '');
  const limitedDigits = digits.slice(0, 8);
  if (limitedDigits.length === 0) return '';
  if (limitedDigits.length <= 2) return limitedDigits;
  if (limitedDigits.length <= 4) return `${limitedDigits.slice(0, 2)}.${limitedDigits.slice(2)}`;
  return `${limitedDigits.slice(0, 2)}.${limitedDigits.slice(2, 4)}.${limitedDigits.slice(4)}`;
};

// Конвертация ДД.ММ.ГГГГ → ГГГГ-ММ-ДД
export const convertDateToISO = (dateStr: string): string => {
  if (!dateStr || dateStr.length !== 10) return '';
  const [day, month, year] = dateStr.split('.');
  if (!day || !month || !year || year.length !== 4) return '';
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
};

// Конвертация ГГГГ-ММ-ДД → ДД.ММ.ГГГГ
export const convertDateFromISO = (isoStr: string): string => {
  if (!isoStr) return '';
  const [year, month, day] = isoStr.split('-');
  if (!year || !month || !day) return '';
  return `${day}.${month}.${year}`;
};

// =====================================================================
// DEPARTMENT RESOLUTION (extracted from AppointmentWizardV2)
// =====================================================================

interface DeptServiceLike {
  id?: unknown;
  queue_tag?: unknown;
  category_code?: string;
  service_code?: unknown;
  name?: unknown;
  [key: string]: unknown;
}

const DEPARTMENT_CODE_MAPPING: Record<string, string> = {
  'K': 'cardiology', // Кардиология → вкладка cardio (БЕЗ ЭКГ!)
  'D': 'dermatology', // Дерматология → вкладка derma (только консультации)
  'S': 'dentistry', // Стоматология → вкладка dental
  'L': 'laboratory', // Лаборатория → вкладка lab
  'P': 'procedures', // Физиотерапия → вкладка procedures
  'C': 'procedures', // Косметология → вкладка procedures
  'D_PROC': 'procedures', // Дерматологические процедуры → вкладка procedures
  'O': 'procedures' // Прочие процедуры → вкладка procedures
};

const DEPARTMENT_NORMALIZED_MAPPING: Record<string, string> = {
  'specialists': 'cardiology', // Консультации специалистов (только если не 'D' или 'S') -> cardiology
  'laboratory': 'lab', // ✅ Лаборатория -> lab (для соответствия вкладке)
  'procedures': 'procedures', // Процедуры -> procedures
  'other': 'general' // Прочее -> general
};

// Определяет отделение визита для услуги (ECG — отдельный кабинет).
// Чистая функция: извлечена из AppointmentWizardV2 (PR-45 LOC ceiling).
export const getWizardDepartmentForService = (
  serviceId: string | number,
  servicesData: DeptServiceLike[]
): string => {
  if (!serviceId || serviceId === null || serviceId === undefined) {
    return 'general';
  }

  const service = servicesData.find((s) => s.id === serviceId);

  if (!service) {
    return 'general';
  }

  // 🎯 СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ ЭКГ: отдельный кабинет!
  if (service.queue_tag === 'ecg') {
    return 'echokg';
  }

  // Сначала точный маппинг оригинального category_code (Bug 2 fix),
  // затем нормализованный fallback.
  if (service.category_code && DEPARTMENT_CODE_MAPPING[service.category_code]) {
    return DEPARTMENT_CODE_MAPPING[service.category_code];
  }

  const normalizedCategoryCode = service.category_code
    ? normalizeCategoryCode(service.category_code)
    : '';

  return (
    DEPARTMENT_NORMALIZED_MAPPING[normalizedCategoryCode] ||
    DEPARTMENT_CODE_MAPPING[service.category_code as string] ||
    'general'
  );
};

// =====================================================================
// PATIENT ID RESOLUTION
// =====================================================================

interface InitialDataLike {
  patient_id?: unknown;
  patient?: { id?: unknown } | null;
  [key: string]: unknown;
}

export const resolveInitialPatientId = (initialData: InitialDataLike | null | undefined): unknown =>
  initialData?.patient_id ?? initialData?.patient?.id ?? null;

// =====================================================================
// DEPARTMENT / CATEGORY MAPPING
// =====================================================================

// PR-25: Legacy hardcoded filter map — kept as fallback.
// Primary path is now dynamic: getWizardDepartmentFilterKeys accepts
// an optional queueProfiles param and builds the filter from
// profile.queue_tags dynamically.
const WIZARD_DEPARTMENT_FILTER_KEYS_FALLBACK = {
  cardio: ['cardio'],
  cardiology: ['cardio', 'cardiology'],
  echokg: ['cardio', 'echokg', 'ecg'],
  ecg: ['cardio', 'echokg', 'ecg'],
  derma: ['derma', 'dermatology'],
  dermatology: ['derma', 'dermatology'],
  dental: ['dental', 'dentistry', 'stomatology'],
  dentistry: ['dental', 'dentistry', 'stomatology'],
  stomatology: ['dental', 'dentistry', 'stomatology'],
  lab: ['lab', 'laboratory'],
  laboratory: ['lab', 'laboratory'],
  procedures: ['procedures'],
  procedure: ['procedures'],
};

// PR-25: backward-compatible export (used by existing code)
export const WIZARD_DEPARTMENT_FILTER_KEYS = WIZARD_DEPARTMENT_FILTER_KEYS_FALLBACK;

/**
 * PR-25: Returns filter keys for a given department/tab.
 *
 * When queueProfiles is provided (array from /queues/profiles), uses
 * the profile's queue_tags dynamically — so new departments work
 * without code changes.
 *
 * When queueProfiles is not provided, falls back to the hardcoded map.
 *
 * @param {string} value - tab key (e.g. 'cardio', 'cosmetology')
 * @param {Array} [queueProfiles] - optional array of {key, queue_tags}
 * @returns {string[]} array of department_key strings to filter by
 */
interface QueueProfileLike {
  key?: unknown;
  queue_tags?: unknown;
  [key: string]: unknown;
}

export const getWizardDepartmentFilterKeys = (
  value: unknown,
  queueProfiles: QueueProfileLike[] | null = null
): string[] => {
  const normalized = String(value || '').trim().toLowerCase();

  // PR-25: dynamic path — use queue_profiles if available
  if (queueProfiles && Array.isArray(queueProfiles) && queueProfiles.length > 0) {
    const profile = queueProfiles.find(
      (p) => String(p.key || '').trim().toLowerCase() === normalized
    );
    if (profile && Array.isArray(profile.queue_tags) && profile.queue_tags.length > 0) {
      return (profile.queue_tags as unknown[]).map((t) => String(t).trim().toLowerCase());
    }
    // If profile exists but has no queue_tags, use the key itself
    if (profile) {
      return [normalized];
    }
  }

  // Fallback to hardcoded map
  return (WIZARD_DEPARTMENT_FILTER_KEYS_FALLBACK as Record<string, string[]>)[normalized] || [normalized];
};

export const serviceCodeToWizardCategory = (value: unknown): 'laboratory' | 'procedures' | 'specialists' | null => {
  const prefix = String(value || '').trim().toUpperCase().charAt(0);
  if (prefix === 'L') return 'laboratory';
  if (prefix === 'P' || prefix === 'C') return 'procedures';
  if (prefix === 'K' || prefix === 'D' || prefix === 'S') return 'specialists';
  return null;
};

export const activeTabToWizardCategory = (value: unknown): 'laboratory' | 'procedures' | 'specialists' => {
  const normalized = String(value || '').trim().toLowerCase();
  if (['lab', 'laboratory'].includes(normalized)) return 'laboratory';
  if (['procedures', 'procedure'].includes(normalized)) return 'procedures';
  return 'specialists';
};

interface ServiceItemLike {
  service_code?: unknown;
  code?: unknown;
  _temp_name?: unknown;
  service_name?: unknown;
  [key: string]: unknown;
}

export const resolveInitialServiceCategory = (
  items: ServiceItemLike[] = [],
  activeTabValue: unknown = ''
): 'laboratory' | 'procedures' | 'specialists' => {
  const firstItem = (Array.isArray(items) ? items : []).find(Boolean) as ServiceItemLike | undefined;
  const itemCategory = serviceCodeToWizardCategory(
    firstItem?.service_code || firstItem?.code || firstItem?._temp_name || firstItem?.service_name
  );
  return itemCategory || activeTabToWizardCategory(activeTabValue);
};

// =====================================================================
// CATEGORIES (for service tabs)
// =====================================================================

export const categories = [
  { id: 'specialists', label: 'Специалисты', icon: Stethoscope },
  { id: 'laboratory', label: 'Лаборатория', icon: FlaskConical },
  { id: 'procedures', label: 'Процедуры', icon: Syringe },
  { id: 'other', label: 'Прочее', icon: ClipboardList },
];

// =====================================================================
// CSS KEYFRAMES (injected once into document head)
// =====================================================================

const wizardKeyframes = `
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
`;

// Inject keyframes into the document (once, with id guard)
if (typeof document !== 'undefined' && !document.getElementById('wizard-keyframes')) {
  const style = document.createElement('style');
  style.id = 'wizard-keyframes';
  style.textContent = wizardKeyframes;
  document.head.appendChild(style);
}

export default {
  PATIENT_NAME_PATTERN,
  MIXED_REPEAT_WARNING,
  STEP_PATIENT,
  STEP_CART,
  TOTAL_STEPS,
  getLocalISODate,
  normalizeWizardContractValue,
  getWizardRecordKind,
  getWizardSourceKind,
  hasQueueIdentityValue,
  resolveExplicitQueueEntryId,
  getFirstQueueNumberId,
  resolveOnlineQueueEntryId,
  getRemovedQueueEntryIds,
  cancelRemovedQueueEntries,
  normalizeServiceSelectionValue,
  normalizeServiceSelectionName,
  normalizeGenderForForm,
  firstNonEmpty,
  resolvePatientGenderValue,
  genderToPatientSexForApi,
  buildCartQuoteRequest,
  formatBirthDateInput,
  convertDateToISO,
  convertDateFromISO,
  getWizardDepartmentForService,
  resolveInitialPatientId,
  WIZARD_DEPARTMENT_FILTER_KEYS,
  getWizardDepartmentFilterKeys,
  serviceCodeToWizardCategory,
  activeTabToWizardCategory,
  resolveInitialServiceCategory,
  categories,
};
