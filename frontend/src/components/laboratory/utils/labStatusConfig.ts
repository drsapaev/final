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
  { key: 'DRAFT',       label: 'Черновик',          variant: 'warning' },
  { key: 'IN_PROGRESS', label: 'Заполняется',       variant: 'primary' },
  { key: 'READY',       label: 'Готов к проверке',  variant: 'primary' },
  { key: 'FINALIZED',   label: 'Утверждён',         variant: 'success' },
  { key: 'PRINTED',     label: 'Напечатан',         variant: 'success' },
];

// Быстрый lookup по ключу статуса.
export const LAB_REPORT_STATUS_BY_KEY = LAB_REPORT_STATUS_CONFIG.reduce(
  (acc, item) => {
    acc[item.key] = item;
    return acc;
  },
  {}
);

// ────────────────────────────────────────────────────────────────────────────
// Статусы очереди (appointment/queue status). Не имеют порядка stepper'а —
// это state machine очереди, а не бланка.
// ────────────────────────────────────────────────────────────────────────────
export const LAB_QUEUE_STATUS_CONFIG = {
  waiting:     { label: 'Ожидает',     variant: 'warning' },
  confirmed:   { label: 'Подтверждён', variant: 'warning' },
  pending:     { label: 'Ожидает',     variant: 'warning' },
  called:      { label: 'Вызван',      variant: 'primary' },
  in_progress: { label: 'В работе',    variant: 'primary' },
  completed:   { label: 'Завершён',    variant: 'success' },
  done:        { label: 'Завершён',    variant: 'success' },
};

/**
 * Возвращает конфигурацию статуса (label + variant) по ключу.
 * Поддерживает как статусы бланка (DRAFT/IN_PROGRESS/...), так и статусы
 * очереди (waiting/called/...). Если статус неизвестен — fallback.
 *
 * @param {string} status — ключ статуса
 * @returns {{ label: string, variant: string }}
 */
export function getLabStatusConfig(status) {
  if (!status) {
    return { label: 'Неизвестно', variant: 'info' };
  }
  return (
    LAB_REPORT_STATUS_BY_KEY[status]
    || LAB_QUEUE_STATUS_CONFIG[status]
    || { label: status, variant: 'info' }
  );
}

/**
 * Возвращает человекочитаемый label статуса.
 * Заменяет старую formatLabStatus() из labUiLabels.js.
 */
export function formatLabStatusLabel(status) {
  return getLabStatusConfig(status).label;
}

/**
 * Возвращает badge-variant статуса.
 * Заменяет старую getLabStatusVariant() из labUiLabels.js.
 */
export function getLabStatusBadgeVariant(status) {
  return getLabStatusConfig(status).variant;
}

/**
 * Возвращает индекс шага в жизненном цикле бланка (для stepper).
 * -1 — статус не принадлежит жизненному циклу (например, status очереди).
 */
export function getLabReportStepIndex(status) {
  if (!status) return -1;
  return LAB_REPORT_STATUS_CONFIG.findIndex((s) => s.key === status);
}
