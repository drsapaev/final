/**
 * i18n/terminology.js — canonical medical terminology map.
 *
 * Single source of truth for core medical/domain terms.
 * Every panel must use these canonical translations — no ad-hoc variants.
 *
 * Problem this solves:
 *   Without a canonical map, "Patient" appears as:
 *     - "Пациент" (nominative)
 *     - "Пациента" (accusative)
 *     - "Пациенты" (plural)
 *     - "пациент" (lowercase)
 *     - "ПАЦИЕНТ" (uppercase)
 *   across different panels, making consistent translation impossible.
 *
 * Solution:
 *   - Define ONE canonical term per concept.
 *   - Use grammatical variants only when the language actually requires them
 *     (e.g., Russian accusative for "Удалить пациента" — encoded as a separate key).
 *   - All panels reference these terms, not invent their own.
 *
 * Usage:
 *   import { TERM } from '../i18n/terminology';
 *   // In a locale file:
 *   patient: TERM.patient.ru,  // → 'Пациент'
 *   // In a component (via t()):
 *   t('terms.patient')
 *
 * Adding a new term:
 *   1. Add it to TERM with all 5 language codes.
 *   2. Add a `terms.<key>` entry to each locale file (ru/uz-Latn/uz-Cyrl/en/kk).
 *   3. Run `node scripts/i18n/validate_locales.js` to verify parity.
 */

export const TERM = {
  patient: {
    ru: 'Пациент',
    'uz-Latn': 'Bemor',
    'uz-Cyrl': 'Бемор',
    en: 'Patient',
    kk: 'Пациент',
  },
  visit: {
    ru: 'Визит',
    'uz-Latn': 'Tashrif',
    'uz-Cyrl': 'Ташриф',
    en: 'Visit',
    kk: 'Визит',
  },
  encounter: {
    ru: 'Приём',
    'uz-Latn': 'Qabul',
    'uz-Cyrl': 'Қабул',
    en: 'Encounter',
    kk: 'Қабылдау',
  },
  appointment: {
    ru: 'Запись',
    'uz-Latn': 'Yozilish',
    'uz-Cyrl': 'Ёзилиш',
    en: 'Appointment',
    kk: 'Жазылым',
  },
  medical_record: {
    ru: 'Медицинская карта',
    'uz-Latn': 'Tibbiy karta',
    'uz-Cyrl': 'Тиббий карта',
    en: 'Medical record',
    kk: 'Медициналық карта',
  },
  emr: {
    ru: 'ЭМК',
    'uz-Latn': 'EMK',
    'uz-Cyrl': 'ЭМК',
    en: 'EMR',
    kk: 'ЭМК',
  },
  queue: {
    ru: 'Очередь',
    'uz-Latn': 'Navbat',
    'uz-Cyrl': 'Навбат',
    en: 'Queue',
    kk: 'Кезек',
  },
  laboratory: {
    ru: 'Лаборатория',
    'uz-Latn': 'Laboratoriya',
    'uz-Cyrl': 'Лаборатория',
    en: 'Laboratory',
    kk: 'Зертхана',
  },
  cashier: {
    ru: 'Касса',
    'uz-Latn': 'Kassa',
    'uz-Cyrl': 'Касса',
    en: 'Cashier',
    kk: 'Касса',
  },
  registrar: {
    ru: 'Регистратура',
    'uz-Latn': 'Registratura',
    'uz-Cyrl': 'Регистратура',
    en: 'Registrar',
    kk: 'Тіркеу',
  },
  doctor: {
    ru: 'Врач',
    'uz-Latn': 'Shifokor',
    'uz-Cyrl': 'Шифокор',
    en: 'Doctor',
    kk: 'Дәрігер',
  },
  admin: {
    ru: 'Администратор',
    'uz-Latn': 'Administrator',
    'uz-Cyrl': 'Администратор',
    en: 'Administrator',
    kk: 'Әкімші',
  },
  diagnosis: {
    ru: 'Диагноз',
    'uz-Latn': 'Tashxis',
    'uz-Cyrl': 'Ташхис',
    en: 'Diagnosis',
    kk: 'Диагноз',
  },
  prescription: {
    ru: 'Рецепт',
    'uz-Latn': 'Retsept',
    'uz-Cyrl': 'Рецепт',
    en: 'Prescription',
    kk: 'Рецепт',
  },
  payment: {
    ru: 'Оплата',
    'uz-Latn': "To'lov",
    'uz-Cyrl': "Тўлов",
    en: 'Payment',
    kk: 'Төлем',
  },
  receipt: {
    ru: 'Чек',
    'uz-Latn': 'Chek',
    'uz-Cyrl': 'Чек',
    en: 'Receipt',
    kk: 'Чек',
  },
  ticket: {
    ru: 'Талон',
    'uz-Latn': 'Talon',
    'uz-Cyrl': 'Талон',
    en: 'Ticket',
    kk: 'Талон',
  },
  report: {
    ru: 'Отчёт',
    'uz-Latn': 'Hisobot',
    'uz-Cyrl': 'Ҳисобот',
    en: 'Report',
    kk: 'Есеп',
  },
  template: {
    ru: 'Шаблон',
    'uz-Latn': 'Shablon',
    'uz-Cyrl': 'Шаблон',
    en: 'Template',
    kk: 'Үлгі',
  },
};

/**
 * Get a canonical term in the specified language.
 * Falls back to Russian, then to the key itself.
 */
export function getTerm(key, language) {
  const term = TERM[key];
  if (!term) return key;
  return term[language] || term.ru || key;
}

export default TERM;
