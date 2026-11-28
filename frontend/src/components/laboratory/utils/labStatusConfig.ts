/**
 * L-H-3 fix: единый источник истины для статусов лабораторного бланка.
 *
 * Раньше маппинг статусов был размазан по 3 файлам:
 *   - labUiLabels.js: _statusLabels (ru-строки) + getLabStatusVariant (badge-variant)
 *   - LabStatusStepper.jsx: LAB_REPORT_STEPS (порядок для stepper)
 *   - getLabLabels(t) в том же labUiLabels.js: i18n-версия
 *
 * Любое изменение требовало правки в 3 местах — рассинхрон был неизбежен.
 * Теперь все знают о едином LAB_REPORT_STATUS_CONFIG и производных.
 *
 * Backend контракт (lab_reporting_service.py): статусы идут строго в порядке
 * DRAFT → IN_PROGRESS → READY → FINALIZED → PRINTED. Это и есть "жизненный
 * цикл" бланка, который отображает stepper.
 *
 * Не путать с очередью: статусы очереди (waiting/confirmed/pending/called/
 * in_progress/completed/done) — отдельный домен, к ним относится только
 * formatLabStatus()/getLabStatusVariant() (т.к. в UI они показываются вместе).
 */

// ────────────────────────────────────────────────────────────────────────────
// Жизненный цикл бланка (instance status). Порядок = порядок stepper'а.
// ────────────────────────────────────────────────────────────────────────────
export const LAB_REPORT_STATUS_CONFIG = [
  { key: 'DRAFT', label: 'Черновик', variant: 'warning', translationKey: 'status.draft' },
  { key: 'IN_PROGRESS', label: 'Заполняется', variant: 'primary', translationKey: 'status.in_progress' },
  { key: 'READY', label: 'Готов к проверке', variant: 'primary', translationKey: 'status.ready' },
  { key: 'IN_REVIEW', label: 'На проверке', variant: 'warning', translationKey: 'workbench.workflow_status_in_review' },
  { key: 'REVIEWED', label: 'Проверен', variant: 'primary', translationKey: 'workbench.workflow_status_reviewed' },
  { key: 'FINALIZED', label: 'Утверждён', variant: 'success', translationKey: 'status.finalized' },
  { key: 'PRINTED', label: 'Напечатан', variant: 'success', translationKey: 'status.printed' },
];

type LabStatusConfig = { label: string; variant: string; translationKey?: string };
export type LabStatusTranslator = (key: string, options?: Record<string, unknown>) => string;

// Быстрый lookup по ключу статуса.
export const LAB_REPORT_STATUS_BY_KEY = LAB_REPORT_STATUS_CONFIG.reduce(
  (acc, item) => {
    acc[item.key] = item;
    return acc;
  },
  {} as Record<string, (typeof LAB_REPORT_STATUS_CONFIG)[number]>
);

// ────────────────────────────────────────────────────────────────────────────
// Статусы очереди (appointment/queue status). Не имеют порядка stepper'а —
// это state machine очереди, а не бланка.
// ────────────────────────────────────────────────────────────────────────────
export const LAB_QUEUE_STATUS_CONFIG = {
  waiting: { label: 'Ожидает', variant: 'warning', translationKey: 'queue_status.waiting' },
  confirmed: { label: 'Подтверждён', variant: 'warning', translationKey: 'queue_status.confirmed' },
  pending: { label: 'Ожидает', variant: 'warning', translationKey: 'queue_status.pending' },
  called: { label: 'Вызван', variant: 'primary', translationKey: 'queue_status.called' },
  in_progress: { label: 'В работе', variant: 'primary', translationKey: 'queue_status.in_progress' },
  completed: { label: 'Завершён', variant: 'success', translationKey: 'queue_status.completed' },
  done: { label: 'Завершён', variant: 'success', translationKey: 'queue_status.done' },
};

/**
 * Возвращает конфигурацию статуса (label + variant) по ключу.
 * Поддерживает как статусы бланка (DRAFT/IN_PROGRESS/...), так и статусы
 * очереди (waiting/called/...). Если статус неизвестен — fallback.
 *
 * @param {string} status — ключ статуса
 * @returns {{ label: string, variant: string }}
 */
export function getLabStatusConfig(status: string): LabStatusConfig {
  if (!status) {
    return { label: 'Неизвестно', variant: 'info', translationKey: 'status.unknown' };
  }
  return (
    LAB_REPORT_STATUS_BY_KEY[status]
    || (LAB_QUEUE_STATUS_CONFIG as Record<string, LabStatusConfig>)[status]
    || { label: status, variant: 'info' }
  );
}

/**
 * Возвращает человекочитаемый label статуса.
 * Заменяет старую formatLabStatus() из labUiLabels.js.
 */
export function formatLabStatusLabel(status: string, translate?: LabStatusTranslator) {
  const { label, translationKey } = getLabStatusConfig(status);
  return translationKey && translate ? translate(translationKey, { defaultValue: label }) : label;
}

/**
 * Возвращает badge-variant статуса.
 * Заменяет старую getLabStatusVariant() из labUiLabels.js.
 */
export function getLabStatusBadgeVariant(status: string) {
  return getLabStatusConfig(status).variant;
}

/**
 * Возвращает индекс шага в жизненном цикле бланка (для stepper).
 * -1 — статус не принадлежит жизненному циклу (например, status очереди).
 */
export function getLabReportStepIndex(status: string) {
  if (!status) return -1;
  return LAB_REPORT_STATUS_CONFIG.findIndex((s) => s.key === status);
}
