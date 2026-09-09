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
// BIRTH DATE CALENDAR VALIDATION (Fix E)
// ==============================================================
export type BirthDateValidation = 'empty' | 'incomplete' | 'invalid' | 'future' | 'ok';

// Календарная валидация даты рождения в формате ДД.ММ.ГГГГ.
// Раньше проверялись только диапазоны 1..31 / 1..12 / год 1900..текущий —
// несуществующие даты (31.02.2020) и будущие даты в текущем году проходили.
// Неполный ввод ('31.02', '3102') не считается валидным — он не должен
// молча превращаться в пустую дату.
export const getBirthDateValidationError = (
  value: string,
  now: Date = new Date()
): BirthDateValidation => {
  const trimmed = String(value || '').trim();
  if (!trimmed || trimmed === '00.00.0000') return 'empty';

  const parts = trimmed.split('.');
  if (parts.length !== 3 || parts.some((part) => part.length === 0)) {
    return 'incomplete';
  }
  const day = Number(parts[0]);
  const month = Number(parts[1]);
  const year = Number(parts[2]);
  if (!Number.isFinite(day) || !Number.isFinite(month) || !Number.isFinite(year)) {
    return 'incomplete';
  }
  if (parts[2].length !== 4) return 'incomplete';

  if (month < 1 || month > 12) return 'invalid';
  if (day < 1 || day > 31) return 'invalid';
  if (year < 1900) return 'invalid';

  // Календарная существованность: Date нормализует переполнения
  // (31.02 → 3 марта), поэтому сверяем компоненты обратно.
  const probe = new Date(year, month - 1, day);
  if (
    probe.getFullYear() !== year ||
    probe.getMonth() !== month - 1 ||
    probe.getDate() !== day
  ) {
    return 'invalid';
  }

  // Будущая дата (полная дата, а не только год)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (probe > today) return 'future';

  return 'ok';
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
  // Codex R3 PR 3095 (P1): привязка подтверждённой квоты к команде сохранения.
  // Заполняется ТОЛЬКО для pricing_mode='cart' (save /registrar/cart
  // перепроверяет цены/настройки на момент подтверждения — расхождение даёт
  // 409 «цены изменились» вместо тихого invoice на другую сумму).
  quote_token?: string;
}

export type CartQuoteStatus = 'idle' | 'loading' | 'ready' | 'error';

interface QuoteCartSource {
  items?: Array<{ service_id?: unknown; quantity?: unknown; custom_price?: unknown; doctor_id?: unknown }>;
  discount_mode?: unknown;
  all_free?: unknown;
}

// Строит запрос квоты из корзины. null — когда нет ни одной позиции
// с разрешённым service_id (квотировать нечего).
export interface CartQuoteRequestOptions {
  // Fix D (Codex R1 #3095): edit-режим квотирует РОВНО edit-delta payload
  // (pricing_mode='edit_delta' зеркалирует правила /registrar/cart/edit-delta).
  // Codex R2 #3095 (P1): 'full_update' — правила /queue/online-entry/{id}/
  // full-update (консультация при repeat/benefit → 0, all_free → 0, остальное
  // — каталог-цена); выбирается по фактическому маршруту команды.
  pricingMode?: 'cart' | 'edit_delta' | 'full_update';
  itemsOverride?: QuoteCartSource['items'];
  // Codex R6 #3095 (P2): edit-delta контекст — квота биллит ту же дельту,
  // что и команда (активная запись того же дня, уже содержащая услугу,
  // биллит max(запрошено − есть, 0)). Передаётся только для edit_delta.
  patientId?: number | string | null;
  targetDate?: string | null;
  preferredEntryIds?: Array<number | string>;
}

export const buildCartQuoteRequest = (
  cart: QuoteCartSource | null | undefined,
  options: CartQuoteRequestOptions = {}
): { items: Array<{ service_id: number; quantity: number; custom_price?: number; specialist_id?: number; queue_entry_id?: number }>; discount_mode: string; all_free: boolean; pricing_mode: string; patient_id?: number; target_date?: string; preferred_entry_ids?: number[] } | null => {
  const rawItems = (options.itemsOverride ?? (Array.isArray(cart?.items) ? cart.items : [])) || [];
  const items = rawItems
    .filter((item) => item && item.service_id != null)
    .map((item) => {
      const quoteItem: { service_id: number; quantity: number; custom_price?: number; specialist_id?: number; queue_entry_id?: number } = {
        service_id: Number(item.service_id),
        quantity: Math.max(1, Number(item.quantity || 1)),
      };
      // Codex R1 #3095 (P2): custom_price зеркалится в квоту (cart-режим)
      const customPrice = (item as { custom_price?: unknown }).custom_price;
      if (customPrice != null && Number.isFinite(Number(customPrice))) {
        quoteItem.custom_price = Number(customPrice);
      }
      // Codex R12 #3095 (P2): specialist_id зеркалится в квоту — маршрутизация
      // дельты в квоте обязана совпадать с маршрутизацией команды (ADR-001).
      // Источники: item.specialist_id у edit-delta target-item'ов (для
      // существующих позиций — null: перенос врача запрещён), иначе
      // doctor_id сырой корзины — ТО ЖЕ, что шлёт команда сохранения
      // (newServices: specialist_id: item.doctor_id). Иначе edit добавляет
      // услугу без default-врача каталога и без активной очереди дня: квота
      // отвечает 400 "specialist_id is required", хотя команда создала бы
      // очередь выбранного врача — завершение заблокировано навсегда.
      // Save-ревалидация токена пере-считывает квоту по ЭТИМ ЖЕ item'ам —
      // зеркалирование в маппере покрывает оба пути одним местом.
      const itemRecord = item as Record<string, unknown>;
      const specialistId = 'specialist_id' in itemRecord ? itemRecord.specialist_id : itemRecord.doctor_id;
      if (specialistId != null && Number.isFinite(Number(specialistId)) && Number(specialistId) > 0) {
        quoteItem.specialist_id = Number(specialistId);
      }
      // Codex R8 #3115 (P1): идентичность исходной записи зеркалится в квоту
      const queueEntryId = (item as { queue_entry_id?: unknown }).queue_entry_id
        ?? (item as { original_queue_id?: unknown }).original_queue_id;
      if (queueEntryId != null && Number.isFinite(Number(queueEntryId)) && Number(queueEntryId) > 0) {
        quoteItem.queue_entry_id = Number(queueEntryId);
      }
      return quoteItem;
    });
  if (items.length === 0) return null;
  const request: { items: Array<{ service_id: number; quantity: number; custom_price?: number; specialist_id?: number; queue_entry_id?: number }>; discount_mode: string; all_free: boolean; pricing_mode: string; patient_id?: number; target_date?: string; preferred_entry_ids?: number[] } = {
    items,
    discount_mode: String(cart?.discount_mode || 'none'),
    all_free: Boolean(cart?.all_free),
    pricing_mode: options.pricingMode || 'cart',
  };
  // Codex R6 #3095 (P2): edit-delta контекст — backend биллит в квоте ту же
  // дельту, которую реально выставит команда (см. _edit_delta_billable_quantity).
  if (options.pricingMode === 'edit_delta') {
    const patientIdNum = Number(options.patientId);
    if (options.patientId != null && Number.isFinite(patientIdNum) && patientIdNum > 0) {
      request.patient_id = patientIdNum;
    }
    if (options.targetDate) {
      request.target_date = String(options.targetDate);
    }
    const entryIds = (options.preferredEntryIds || [])
      .map((id) => Number(id))
      .filter((id) => Number.isFinite(id) && id > 0);
    if (entryIds.length > 0) {
      request.preferred_entry_ids = entryIds;
    }
  }
  return request;
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
// PATIENT SELECTION SAFETY (Fix A: data mixing / duplicate-phone stop)
// =====================================================================

// Marker set by the wizard when ALL patient fields were populated from an
// explicitly selected card (selectPatient). Editing ФИО afterwards switches
// the form to new-patient mode and must clear every inherited field,
// otherwise a new patient is created with another person's address/phone.
export const PATIENT_SELECTED_FROM_CARD_FLAG = '_selectedFromCard';

export const isPatientSelectedFromCard = (
  patient: Record<string, unknown> | null | undefined
): boolean => Boolean(patient && patient[PATIENT_SELECTED_FROM_CARD_FLAG]);

// Identity fields that must never leak from one patient card into a
// different patient's registration. Returned as a patch for spread.
export const buildInheritedPatientClearPatch = (): Record<string, unknown> => ({
  birth_date: '',
  phone: '',
  address: '',
  gender: '',
  lastName: '',
  firstName: '',
  middleName: '',
  [PATIENT_SELECTED_FROM_CARD_FLAG]: false,
});

// Backend currently signals "duplicate phone" with HTTP 400 + a text detail.
// The same 400 is also used for unrelated validation problems (e.g. duplicate
// doc_number), so only an explicit phone-duplicate message may trigger the
// duplicate-phone UX path. Until the backend exposes a dedicated error code,
// this is the narrowest safe discriminator.
export const isPhoneDuplicateErrorMessage = (message: unknown): boolean => {
  const normalized = String(message || '').toLowerCase();
  return normalized.includes('уже существует') && normalized.includes('телефон');
};

// IDEMPOTENCY KEY (Fix C: duplicate submit / lost-response retry)
// =====================================================================

// Один логический сабмит корзины = один Idempotency-Key. При потере ответа
// и повторной отправке с тем же ключом backend вернёт кэшированный ответ
// (IdempotencyMiddleware), а не создаст вторую корзину.
export const createIdempotencyKey = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `cart-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
};

// Codex R2 PR 3092 (P1): ключ привязан к снимку payload первой попытки.
// Чистая гвардия: 'bind' — первая попытка (ключ + снимок), 'proceed' —
// повтор с теми же данными (кэш backend вернёт сохранённый ответ),
// 'block' — повтор с ИЗМЕНЁННЫМИ данными и старым ключом (backend вернёт 409,
// оригинальный успех нельзя натянуть на новые данные).
export type CartIdempotencyGuardAction = 'bind' | 'proceed' | 'block';
export interface CartIdempotencyGuardArgs {
  existingKey: string | null;
  existingPayload: string | null;
  payload: string;
  newKey: string;
}
export interface CartIdempotencyGuardResult {
  action: CartIdempotencyGuardAction;
  key: string | null;
  payload: string | null;
}
export const cartIdempotencyGuard = (args: CartIdempotencyGuardArgs): CartIdempotencyGuardResult => {
  if (!args.existingKey) {
    return { action: 'bind', key: args.newKey, payload: args.payload };
  }
  if (args.existingPayload != null && args.existingPayload !== args.payload) {
    return { action: 'block', key: args.existingKey, payload: args.existingPayload };
  }
  return { action: 'proceed', key: args.existingKey, payload: args.existingPayload };
};

// Общие стили тостов Fix C (токены --mac-*; общий модуль = без дублирования).
export const TOAST_WARNING_STYLE = {
  backgroundColor: 'color-mix(in srgb, var(--mac-warning), transparent 84%)',
  border: '1px solid color-mix(in srgb, var(--mac-warning), transparent 72%)',
  color: 'var(--mac-text-primary)'
} as const;

export const TOAST_ERROR_STYLE = {
  backgroundColor: 'color-mix(in srgb, var(--mac-error), transparent 84%)',
  border: '1px solid color-mix(in srgb, var(--mac-error), transparent 72%)',
  color: 'var(--mac-text-primary)'
} as const;

// =====================================================================
// CART GROUPING BY VISIT (вынесено из AppointmentWizardV2 без изменения логики)
// =====================================================================

export interface WizardCartItemLike {
  service_id?: unknown;
  doctor_id?: unknown;
  quantity?: number;
  original_queue_id?: string | number | null;
  service_code?: string | null;
  service_name?: string | null;
  name?: string | null;
  visit_date?: string;
  visit_time?: string | null;
  _source?: string | null;
  [key: string]: unknown;
}

export interface GroupedVisitLike {
  doctor_id: string | number | null;
  services: Array<{
    service_id?: string | number;
    quantity?: number;
    original_queue_id?: string | number | null;
    service_code?: string | null;
    service_name?: string | null;
    _source?: string | null;
  }>;
  visit_date?: string;
  visit_time?: string | null;
  department: string;
  notes: string | null;
}

export const groupCartItemsByVisit = (
  items: WizardCartItemLike[],
  getDepartmentByService: (serviceId: string | number) => string,
): GroupedVisitLike[] => {
  const visits: Record<string, GroupedVisitLike> = {};

  // ✅ ИСПРАВЛЕНО: Фильтруем элементы корзины без service_id
  const validItems = items.filter((item) => {
    if (!item.service_id) {
      logger.warn('⚠️ Пропущен элемент корзины без service_id:', item);
      return false;
    }
    return true;
  });

  if (validItems.length === 0) {
    logger.warn('⚠️ Нет валидных элементов в корзине');
    return [];
  }

  validItems.forEach((item) => {
    // Определяем отделение для услуги
    const department = getDepartmentByService(item.service_id as string | number);

    // ✅ ИСПРАВЛЕНО: Объединяем все процедуры в один визит
    // Все процедуры (P, C, D_PROC) должны быть в одном визите с department = 'procedures'
    let finalDepartment = department;
    if (department === 'procedures') {
      finalDepartment = 'procedures'; // Все процедуры в одном отделе
    }

    // Группируем по finalDepartment + doctor_id + visit_date + visit_time
    const key = `${finalDepartment}_${item.doctor_id || 'no_doctor'}_${item.visit_date}_${item.visit_time || 'no_time'}`;

    if (!visits[key]) {
      visits[key] = {
        doctor_id: (item.doctor_id as string | number) || null,
        services: [],
        visit_date: item.visit_date,
        visit_time: item.visit_time || null,
        department: finalDepartment,
        notes: null
      };
    }

    visits[key].services.push({
      service_id: item.service_id as string | number,
      quantity: item.quantity,
      original_queue_id: item.original_queue_id || null,
      service_code: item.service_code || null,
      service_name: item.service_name || item.name || null,
      _source: item._source || null
    });
  });

  return Object.values(visits);
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


// =====================================================================
// FIX D (Codex R1 #3095): ИСХОДНЫЕ УСЛУГИ EDIT-ЗАПИСИ (identity sets)
// =====================================================================

interface WizardServiceRecord {
  id?: string | number;
  name?: string;
  service_code?: string | null;
  [k: string]: unknown;
}

export interface EditOriginalServiceIdentity {
  hasQueueEntries: boolean;
  serviceIds: Set<unknown>;
  serviceCodes: Set<string>;
  serviceNames: Set<string>;
  queueIds: Set<string | number>;
  entryUpdatedAtMap: Record<string, string>;
  // W2-PR1: исходное количество позиции по service_id (из service_details —
  // read-модель отдаёт quantity с W2-PR1). Отсутствие ключа = исходное
  // количество неизвестно — такая позиция не включается в edit-дельту.
  originalQuantities: Map<string, number>;
}

// Собирает множества «исходных» услуг edit-записи (service_details →
// service_codes → services-коды → queue_numbers → services-строки) — ТОТ ЖЕ
// порядок приоритетов и те же нормализации, что были в handleComplete.
// Используется и сабмитом (edit-delta payload), и edit-квотой (Fix D), чтобы
// подтверждение показывало ровно то, что edit-delta выставит в invoice.
export const buildEditOriginalServiceIdentity = (
  editMode: boolean,
  initialData: Record<string, unknown> | null | undefined,
  servicesData: WizardServiceRecord[],
): EditOriginalServiceIdentity => {
  const identity: EditOriginalServiceIdentity = {
    hasQueueEntries: false,
    serviceIds: new Set(),
    serviceCodes: new Set<string>(),
    serviceNames: new Set<string>(),
    queueIds: new Set<string | number>(),
    entryUpdatedAtMap: {},
    originalQuantities: new Map<string, number>(),
  };
  if (!editMode || !initialData) return identity;

  const initialRecordKind = getWizardRecordKind(initialData);
  const initialSourceKind = getWizardSourceKind(initialData);
  const hasQueueEntries = Boolean(initialData) && (
    (Array.isArray(initialData.queue_numbers) && initialData.queue_numbers.length > 0) ||
    initialSourceKind === 'online' ||
    initialSourceKind === 'desk' ||
    initialRecordKind === 'online_queue' ||
    initialRecordKind === 'visit' ||
    initialRecordKind === 'appointment');
  identity.hasQueueEntries = Boolean(hasQueueEntries);
  if (!hasQueueEntries) return identity;

  const originalServiceIds = identity.serviceIds;
  const originalQueueIds = identity.queueIds; // PR-14: optimistic locking map lives here too
  const entryUpdatedAtMap = identity.entryUpdatedAtMap;
  const originalQuantities = identity.originalQuantities;
  const originalServiceCodes = identity.serviceCodes;
  const originalServiceNames = identity.serviceNames;

    // Определяем исходные услуги из initialData
    const serviceDetailOccurrences = new Map<string, number>();

    if (Array.isArray(initialData.service_details) && initialData.service_details.length > 0) {
      logger.log('📋 Извлечение исходных услуг из service_details:', initialData.service_details);
      initialData.service_details.forEach((serviceDetail) => {
        if (!serviceDetail) return;

        const serviceId = serviceDetail.service_id || serviceDetail.id || null;
        const serviceCode = serviceDetail.service_code || serviceDetail.code || null;
        const serviceName = serviceDetail.service_name || serviceDetail.name || null;
        const queueId = resolveExplicitQueueEntryId(serviceDetail, { allowLegacyId: false });

        if (serviceId) originalServiceIds.add(serviceId);
        if (queueId) originalQueueIds.add(queueId);
        // W2-PR1: исходное количество позиции (read-модель service_details)
        const originalQty = Number(serviceDetail.quantity ?? serviceDetail.qty);
        if (serviceId && Number.isFinite(originalQty) && originalQty > 0) {
          // Codex R15 #3115 (P1): ключ — (queue_entry_id, service_id): одна
          // услуга в ДВУХ записях с разными количествами не должна
          // перезаписывать друг друга в карте исходных количеств, иначе
          // правка первой позиции классифицируется no-op по количеству
          // второй. Bare-ключ услуги хранится, пока позиция одна
          // (легаси-потоки без идентичности записи), и снимается при
          // неоднозначности — остаются только точные ключи.
          const bareServiceKey = String(serviceId);
          const detailCount = (serviceDetailOccurrences.get(bareServiceKey) ?? 0) + 1;
          serviceDetailOccurrences.set(bareServiceKey, detailCount);
          originalQuantities.set(`${queueId ?? ''}:${bareServiceKey}`, originalQty);
          if (detailCount === 1) {
            originalQuantities.set(bareServiceKey, originalQty);
          } else {
            originalQuantities.delete(bareServiceKey);
          }
        }
        // PR-14: collect updated_at for optimistic locking
        if (queueId) {
          const ts = serviceDetail.updated_at || serviceDetail.last_changed_at || initialData.updated_at || initialData.last_changed_at;
          if (ts) entryUpdatedAtMap[queueId] = ts;
        }
        if (serviceCode) originalServiceCodes.add(String(serviceCode).toUpperCase().trim());
        if (serviceName) originalServiceNames.add(String(serviceName).toLowerCase().trim());
      });
    }

    // ✅ ПРИОРИТЕТ 1: service_codes - наиболее надежный источник для записей типа visit
    if (Array.isArray(initialData.service_codes) && initialData.service_codes.length > 0) {
      logger.log('📋 Извлечение услуг из service_codes:', initialData.service_codes);
      initialData.service_codes.forEach((code) => {
        if (code) {
          const normalizedCode = code.toUpperCase().trim();
          originalServiceCodes.add(normalizedCode);
          // Находим service_id по service_code
          const service = servicesData.find((s) => {
            if (!s.service_code) return false;
            const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
            const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');
            const codeNoZero = normalizedCode.replace(/^([A-Z])0+(\d+)$/, '$1$2');
            return serviceCodeUpper === normalizedCode || serviceCodeNoZero === codeNoZero;
          });
          if (service) {
            originalServiceIds.add(service.id);
            originalServiceNames.add(String(service.name ?? '').toLowerCase().trim());
            logger.log(`  ✅ Найден service_id=${service.id} для кода "${code}"`);
          } else {
            logger.warn(`  ⚠️ Услуга с кодом "${code}" не найдена в servicesData`);
          }
        }
      });
    }

    // ✅ ПРИОРИТЕТ 1.5: services (если service_codes пуст) - может быть кодами
    // ⚠️ ВАЖНО: services может содержать коды (k01, d05) или имена
    if (originalServiceIds.size === 0 && Array.isArray(initialData.services) && initialData.services.length > 0) {
      logger.log('📋 service_codes пуст, используем services как коды:', initialData.services);
      initialData.services.forEach((serviceValue) => {
        const normalizedRawValue = normalizeServiceSelectionValue(serviceValue);
        const normalizedRawName = normalizeServiceSelectionName(serviceValue);

        if (normalizedRawValue || normalizedRawName) {
          const normalizedValue = normalizedRawValue.toUpperCase().trim();

          // ✅ Сначала пробуем найти по service_code (коды типа 'k01', 'd05')
          // ⚠️ ВАЖНО: Коды могут быть в формате 'K01', 'k01', 'K01: Название' и т.д.
          let service = servicesData.find((s) => {
            if (!s.service_code) return false;
            const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
            // Убираем ведущие нули для сравнения (k01 = k1)
            const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');
            const valueNoZero = normalizedValue.replace(/^([A-Z])0+(\d+)$/, '$1$2');

            // Прямое сравнение
            if (serviceCodeUpper === normalizedValue) return true;
            // Сравнение без ведущих нулей
            if (serviceCodeNoZero === valueNoZero) return true;
            // Сравнение с учетом возможного формата 'K01: Название'
            const serviceCodeBase = serviceCodeUpper.split(':')[0].trim();
            const valueBase = normalizedValue.split(':')[0].trim();
            if (serviceCodeBase === valueBase) return true;

            return false;
          });

          // Если не нашли по коду, пробуем по имени (fallback)
          if (!service) {
            const normalizedName = normalizedRawName.toLowerCase().trim();
            service = servicesData.find((s) =>
            s.name && s.name.toLowerCase().trim() === normalizedName
            );
          }

          if (service) {
            originalServiceIds.add(service.id);
            if (service.service_code) {
              originalServiceCodes.add(service.service_code.toUpperCase().trim());
            }
            originalServiceNames.add(String(service.name ?? '').toLowerCase().trim());
            logger.log(`  ✅ Найден service_id=${service.id} для "${normalizedRawValue || normalizedRawName}" (код: ${service.service_code || 'нет'}, имя: ${service.name})`);
          } else {
            // ✅ УЛУЧШЕНО: Показываем примеры кодов из servicesData для отладки
            const exampleCodes = servicesData.
            filter((s) => s.service_code).
            slice(0, 10).
            map((s) => `${s.service_code}: ${s.name}`).
            join(', ');
            logger.warn(`  ⚠️ Услуга "${normalizedRawValue || normalizedRawName || '[empty]'}" не найдена в servicesData. Примеры кодов: ${exampleCodes}`);
          }
        }
      });
    }

    // ✅ ПРИОРИТЕТ 2: queue_numbers - основной источник для всех типов записей
    if (Array.isArray(initialData.queue_numbers) && initialData.queue_numbers.length > 0) {
      logger.log('📋 Извлечение услуг из queue_numbers:', initialData.queue_numbers);
      initialData.queue_numbers.forEach((q) => {
        if (q && q.service_id) {
          originalServiceIds.add(q.service_id);
          const queueId = resolveExplicitQueueEntryId(q);
          if (queueId) originalQueueIds.add(queueId); // ✅ Сохраняем ID записи очереди
          // PR-14: collect updated_at for optimistic locking
          if (queueId) {
            const ts = q.updated_at || q.last_changed_at || initialData.updated_at || initialData.last_changed_at;
            if (ts) entryUpdatedAtMap[queueId] = ts;
          }
          // Находим service_code и name по service_id
          const service = servicesData.find((s) => s.id === q.service_id);
          if (service) {
            if (service.service_code) {
              originalServiceCodes.add(service.service_code.toUpperCase().trim());
            }
            originalServiceNames.add(String(service.name ?? '').toLowerCase().trim());
          }
        }
        if (q && q.service_code) {
          const normalizedCode = q.service_code.toUpperCase().trim();
          originalServiceCodes.add(normalizedCode);
          const service = servicesData.find((s) =>
          s.service_code && s.service_code.toUpperCase().trim() === normalizedCode
          );
          if (service) {
            originalServiceIds.add(service.id);
            originalServiceNames.add(String(service.name ?? '').toLowerCase().trim());
          }
        }
        if (q && q.service_name) {
          const normalizedName = q.service_name.toLowerCase().trim();
          originalServiceNames.add(normalizedName);
          const service = servicesData.find((s) =>
          s.name && s.name.toLowerCase().trim() === normalizedName
          );
          if (service) {
            originalServiceIds.add(service.id);
            if (service.service_code) {
              originalServiceCodes.add(service.service_code.toUpperCase().trim());
            }
          }
        }
      });
    }

    // ✅ ПРИОРИТЕТ 3: services (массив строк) - может быть кодами или именами
    if (Array.isArray(initialData.services) && initialData.services.length > 0) {
      logger.log('📋 Извлечение услуг из services:', initialData.services);
      initialData.services.forEach((serviceValue) => {
        const normalizedRawValue = normalizeServiceSelectionValue(serviceValue);
        const normalizedRawName = normalizeServiceSelectionName(serviceValue);

        if (normalizedRawValue || normalizedRawName) {
          const normalizedValue = normalizedRawValue.toUpperCase().trim();
          const normalizedName = normalizedRawName.toLowerCase().trim();

          // ✅ Сначала пробуем найти по service_code (коды типа 'k01', 'd05')
          let service = servicesData.find((s) => {
            if (!s.service_code) return false;
            const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
            // Убираем ведущие нули для сравнения (k01 = k1)
            const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');
            const valueNoZero = normalizedValue.replace(/^([A-Z])0+(\d+)$/, '$1$2');
            return serviceCodeUpper === normalizedValue || serviceCodeNoZero === valueNoZero;
          });

          // Если не нашли по коду, пробуем по имени
          if (!service) {
            service = servicesData.find((s) =>
            s.name && s.name.toLowerCase().trim() === normalizedName
            );
          }

          if (service) {
            originalServiceIds.add(service.id);
            if (service.service_code) {
              originalServiceCodes.add(service.service_code.toUpperCase().trim());
            }
            originalServiceNames.add(String(service.name ?? '').toLowerCase().trim());
            logger.log(`  ✅ Найден service_id=${service.id} для "${normalizedRawValue || normalizedRawName}" (код: ${service.service_code || 'нет'}, имя: ${service.name})`);
          } else {
            logger.warn(`  ⚠️ Услуга "${normalizedRawValue || normalizedRawName || '[empty]'}" не найдена в servicesData (ни по коду, ни по имени)`);
          }
        }
      });
    }

    logger.log('📋 Исходные услуги определены:', {
      serviceIds: Array.from(originalServiceIds),
      serviceCodes: Array.from(originalServiceCodes),
      serviceNames: Array.from(originalServiceNames)
    });

  return identity;
};

// Предикат «новая услуга» для edit-дельты — ТОТ ЖЕ, что в сабмите
// handleComplete (original_queue_id + serviceIds/Codes/Names).
export const isEditDeltaNewItem = (
  item: { original_queue_id?: unknown; service_id?: unknown },
  service: WizardServiceRecord | undefined,
  identity: EditOriginalServiceIdentity,
): boolean => {
  const hasExistingQueueIdentity = Boolean(item.original_queue_id);
  const inIds = identity.serviceIds.has(item.service_id);
  const inCodes = service?.service_code
    ? identity.serviceCodes.has(String(service.service_code).toUpperCase().trim())
    : false;
  const inNames = service?.name
    ? identity.serviceNames.has(String(service.name).toLowerCase().trim())
    : false;
  return !hasExistingQueueIdentity && !inIds && !inCodes && !inNames;
};

// =====================================================================
// W2-PR1: ЦЕЛЕВОЕ СОСТОЯНИЕ edit-дельты (полная корзина, а не только новые)
// =====================================================================

export interface EditDeltaTargetItem {
  service_id: string | number;
  quantity: number;
  specialist_id: string | number | null;
}

export interface EditDeltaTargetBuild {
  items: EditDeltaTargetItem[];
  hasNew: boolean;
  hasQuantityChange: boolean;
}

// Собирает edit-delta payload из ВСЕЙ корзины (целевое состояние позиции),
// а не только из новых услуг. Новые услуги — как раньше (specialist_id из
// корзины). Существующая позиция включается ТОЛЬКО когда исходное количество
// известно (service_details после W2-PR1) и пользователь его изменил:
// неизвестное исходное количество нельзя молча превращать в снижение —
// backend применил бы его как negative delta (записал бы целевое количество
// поверх реального). Позиция без изменения количества не отправляется —
// настоящий no-op. Смена врача существующей позиции в payload не передаётся
// (specialist_id=null): контракт переноса — отдельная операция (wave2 PR2).
export const buildEditDeltaTargetItems = (
  cartItems: Array<Record<string, unknown>>,
  servicesData: WizardServiceRecord[],
  identity: EditOriginalServiceIdentity,
): EditDeltaTargetBuild => {
  const build: EditDeltaTargetBuild = { items: [], hasNew: false, hasQuantityChange: false };
  (cartItems || []).forEach((item) => {
    if (!item || item.service_id == null) return;
    const service = servicesData.find((s) => String(s.id) === String(item.service_id));
    if (!service) return; // зеркало сабмита: услуга вне справочника не сабмитится
    const quantity = Math.max(1, Number(item.quantity || 1));
    if (isEditDeltaNewItem(item, service, identity)) {
      build.hasNew = true;
      build.items.push({
        service_id: item.service_id as string | number,
        quantity,
        specialist_id: (item.doctor_id as string | number | undefined) ?? null,
      });
      return;
    }
    // Codex R15 #3115 (P1): сравнение по ИДЕНТИЧНОСТИ (запись, услуга) —
    // той же, по которой записывались исходные количества из service_details;
    // оригинальная запись берётся из самой корзинной позиции. Bare-ключ —
    // фолбэк для однозначных легаси-потоков без идентичности записи.
    const originalQueueId = item.original_queue_id ?? item.queue_entry_id ?? null;
    const serviceKey = String(item.service_id);
    const originalQty =
      identity.originalQuantities.get(`${originalQueueId ?? ''}:${serviceKey}`) ??
      identity.originalQuantities.get(serviceKey);
    if (originalQty === undefined) return;
    if (quantity === originalQty) return; // без изменений — no-op
    build.hasQuantityChange = true;
    // Codex R8 #3115 (P1): существующая позиция сохраняет идентичность своей
    // записи (original_queue_id из service_details). При одном service_id под
    // разными врачами/записями правится ИМЕННО названная запись, а не
    // ближайшая по глобальному preferred-набору.
    build.items.push({
      service_id: item.service_id as string | number,
      quantity,
      specialist_id: null,
      ...(originalQueueId != null && Number.isFinite(Number(originalQueueId))
        ? { queue_entry_id: Number(originalQueueId) }
        : {}),
    });
  });
  return build;
};

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
  getBirthDateValidationError,
  formatBirthDateInput,
  convertDateToISO,
  convertDateFromISO,
  PATIENT_SELECTED_FROM_CARD_FLAG,
  isPatientSelectedFromCard,
  buildInheritedPatientClearPatch,
  isPhoneDuplicateErrorMessage,
  createIdempotencyKey,
  buildCartQuoteRequest,
  buildEditDeltaTargetItems,
  getWizardDepartmentForService,
  resolveInitialPatientId,
  WIZARD_DEPARTMENT_FILTER_KEYS,
  getWizardDepartmentFilterKeys,
  serviceCodeToWizardCategory,
  activeTabToWizardCategory,
  resolveInitialServiceCategory,
  categories
};