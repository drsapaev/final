// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * Patient Panel — shared utilities.
 *
 * L-H-4 fix: выделены из монолитного PatientPanel.jsx (1138 строк).
 *
 * Содержит:
 *   - readTelegramMiniAppInitData: безопасное чтение Telegram.WebApp.initData
 *   - error message dictionaries + describe*Error helpers
 *   - date helpers для booking form
 *
 * L-M-4 fix (bonus): объединены 3 дублирующих словаря error-messages
 * (bookingErrorMessages, cabinetErrorMessages, patientFormErrorMessages)
 * в один PATIENT_ERROR_MESSAGES с domain-prefix.
 */

// ─── Telegram Mini App identity ────────────────────────────────────────────

export const readTelegramMiniAppInitData = () => {
  if (typeof window === 'undefined') {
    return '';
  }
  const initData = window.Telegram?.WebApp?.initData;
  return typeof initData === 'string' ? initData.trim() : '';
};

// ─── Date helpers ──────────────────────────────────────────────────────────

export const toLocalDateInputValue = (value) => {
  const localDate = new Date(value.getTime() - (value.getTimezoneOffset() * 60_000));
  return localDate.toISOString().slice(0, 10);
};

export const getDefaultAppointmentDate = () => {
  const nextDate = new Date();
  nextDate.setDate(nextDate.getDate() + 1);
  return toLocalDateInputValue(nextDate);
};

export const getTodayDateInputValue = () => toLocalDateInputValue(new Date());

// ─── Services helper ───────────────────────────────────────────────────────
//
// L-L-8 fix: простой split по comma ломается на скобках:
//   "Анализ крови, УЗИ (грудной клетки)" → ["Анализ крови", "УЗИ (грудной клетки)"]
// Теперь split respects parenthesized content — comma inside () не разделяет.
// Это best-effort для user-typed input. Backend должен валидировать отдельно.

export const splitBookingServices = (value) => {
  const text = String(value || '').trim();
  if (!text) return [];

  const result = [];
  let current = '';
  let parenDepth = 0;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '(') parenDepth++;
    else if (char === ')') parenDepth = Math.max(0, parenDepth - 1);

    if (char === ',' && parenDepth === 0) {
      const trimmed = current.trim();
      if (trimmed) result.push(trimmed);
      current = '';
    } else {
      current += char;
    }
  }

  const lastTrimmed = current.trim();
  if (lastTrimmed) result.push(lastTrimmed);

  return result;
};

// ─── Error messages (L-M-4 fix: unified dictionary) ────────────────────────
//
// Раньше было 3 отдельных словаря с пересекающимися ключами:
//   bookingErrorMessages, cabinetErrorMessages, patientFormErrorMessages
// Любое изменение требовало правки в 3 местах — рассинхрон неизбежен.
// Теперь единый PATIENT_ERROR_MESSAGES с domain-prefix.
//
// Домены: 'booking' | 'cabinet' | 'forms' | 'report'

const SHARED_ERROR_MESSAGES = {
  auth_date_expired: 'Откройте Mini App из Telegram заново.',
  hash_mismatch: 'Откройте Mini App из Telegram заново.',
  telegram_link_required: 'Привяжите Telegram к профилю пациента перед выполнением.',
  bot_token_required: 'Telegram Mini App ещё не настроен.',
  init_data_replayed: 'Этот сеанс уже использован. Откройте Mini App из Telegram заново.',
};

const BOOKING_ERROR_MESSAGES = {
  ...SHARED_ERROR_MESSAGES,
  appointment_date_in_past: 'Выберите сегодня или более позднюю дату.',
  appointment_date_invalid: 'Выберите корректную дату записи.',
  appointment_time_invalid: 'Укажите корректное время.',
  appointment_time_slot_occupied: 'Это время у врача уже занято. Выберите другое время или оставьте поле пустым.',
  patient_scope_mismatch: 'Эта заявка на запись не принадлежит привязанному пациенту.',
  patient_scope_required: 'Привяжите Telegram к профилю пациента перед записью.',
};

const CABINET_ERROR_MESSAGES = {
  ...SHARED_ERROR_MESSAGES,
  patient_scope_mismatch: 'Этот кабинет не принадлежит привязанному пациенту.',
  patient_scope_required: 'Привяжите Telegram к профилю пациента перед открытием кабинета.',
};

const FORMS_ERROR_MESSAGES = {
  ...SHARED_ERROR_MESSAGES,
  patient_form_answer_unknown_field: 'Форма изменилась. Перезагрузите Mini App и попробуйте снова.',
  patient_form_answer_type_invalid: 'Один из ответов имеет недопустимое значение. Проверьте форму и попробуйте снова.',
  patient_form_answer_too_long: 'Один из ответов слишком длинный. Сократите его и попробуйте снова.',
  patient_form_answer_required: 'Не заполнен обязательный ответ.',
  patient_scope_mismatch: 'Эта форма не принадлежит привязанному пациенту.',
};

export const PATIENT_ERROR_MESSAGES = {
  booking: BOOKING_ERROR_MESSAGES,
  cabinet: CABINET_ERROR_MESSAGES,
  forms: FORMS_ERROR_MESSAGES,
};

const DEFAULT_ERROR_MESSAGES = {
  booking: 'Не удалось обработать заявку на запись.',
  cabinet: 'Не удалось загрузить кабинет пациента.',
  forms: 'Не удалось сохранить форму. Попробуйте снова из Telegram.',
};

/**
 * Возвращает человекочитаемое сообщение об ошибке по reason-коду.
 * @param {string} domain — 'booking' | 'cabinet' | 'forms'
 * @param {string} reason — reason-код с backend
 * @returns {string}
 */
export function describePatientError(domain, reason) {
  const domainMessages = PATIENT_ERROR_MESSAGES[domain] || {};
  return domainMessages[reason] || DEFAULT_ERROR_MESSAGES[domain] || 'Произошла ошибка.';
}
