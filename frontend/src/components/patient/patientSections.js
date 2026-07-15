/**
 * L-H-4 fix: конфиг секций PatientPanel выделен в отдельный файл.
 *
 * L-H-1 fix: все строки переведены на русский (были на английском).
 * L-H-8 fix: lucide-direct icons заменены на macos <Icon name="...">.
 *
 * Секции определяют навигацию PatientPanel:
 *   booking, payments, forms, documents, doctors, cabinet
 *
 * L-H-6 fix: добавлены visible-tab флаги — определяют, какие секции
 * показываются в tablist-навигации (не все секции имеют UI-экран).
 */

export const PATIENT_SECTIONS = {
  booking: {
    icon: 'calendar',
    title: 'Запись на приём',
    description: 'Защищённая запись открывается из Telegram Mini App.',
    visibleInTabs: true,
  },
  payments: {
    icon: 'doc.text',
    title: 'Платежи и долг',
    description: 'Защищённая сумма платежей открывается из Telegram Mini App.',
    visibleInTabs: true,
  },
  forms: {
    icon: 'doc.text',
    title: 'Анкеты пациента',
    description: 'Защищённый поток анкет будет завершён в Mini App.',
    visibleInTabs: true,
  },
  documents: {
    icon: 'doc.text',
    title: 'Документы',
    description: 'Защищённый поток документов ещё не реализован. Обратитесь в клинику за копиями.',
    visibleInTabs: true,
  },
  doctors: {
    icon: 'stethoscope',
    title: 'Врачи',
    description: 'Выбор врача и продолжение записи — в рамках внедрения Mini App.',
    visibleInTabs: true,
  },
  cabinet: {
    icon: 'doc.text',
    title: 'Личный кабинет',
    description: 'Защищённый личный кабинет открывается из Mini App.',
    visibleInTabs: true,
  },
};

export const PATIENT_SECTION_KEYS = Object.keys(PATIENT_SECTIONS);

export const VISIBLE_PATIENT_TABS = PATIENT_SECTION_KEYS.filter(
  (key) => PATIENT_SECTIONS[key].visibleInTabs
);

export function normalizeSection(value) {
  if (!value) {
    return 'home';
  }
  return PATIENT_SECTIONS[String(value).toLowerCase()]
    ? String(value).toLowerCase()
    : 'home';
}
