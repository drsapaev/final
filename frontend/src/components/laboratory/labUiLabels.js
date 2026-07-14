/**
 * Lab UI labels — static Russian exports.
 *
 * L-H-3 fix: маппинг статусов делегирован в utils/labStatusConfig.js.
 * L-M-6 fix: удалена неиспользуемая getLabLabels(t) i18n-обёртка (была
 * добавлена в PR-73, но ни один компонент в lab-модуле не использует
 * useTranslation — все рендерят русские строки напрямую). Когда i18n
 * будет внедряться на уровне всего проекта, миграция будет единой для
 * всех панелей — не точечно для lab.
 *
 * Usage in components:
 *   import { formatLabStatus, getLabStatusVariant } from './labUiLabels';
 *
 *   // Для stepper / step-index используйте labStatusConfig напрямую:
 *   import { getLabStatusConfig, getLabReportStepIndex } from './utils/labStatusConfig';
 */

import { getLabStatusConfig } from './utils/labStatusConfig';

// ────────────────────────────────────────────────────────────────────────────
// Payment / specialty / severity labels (static Russian).
// Эти домены не входят в labStatusConfig.js — они относятся к разным
// сущностям (оплата, специализация очереди, severity-флаги).
// ────────────────────────────────────────────────────────────────────────────

const _paymentStatusLabels = {
  pending: 'Не оплачено',
  paid: 'Оплачено',
  partial: 'Частично оплачено',
  refunded: 'Возврат',
  cancelled: 'Отменено'
};

const _specialtyLabels = {
  lab: 'Лаборатория',
  laboratory: 'Лаборатория',
  general: 'Общая очередь'
};

const _severityLabels = {
  critical: 'Критично',
  flagged: 'Есть отклонения',
  warning: 'Предупреждение',
  clean: 'Без отклонений'
};

export const signerFieldLabels = {
  lab_technician_label: 'Подпись лаборанта',
  lab_technician_name: 'ФИО лаборанта',
  approver_label: 'Подпись утверждающего',
  approver_name: 'ФИО утверждающего'
};

// L-H-3 fix: formatLabStatus и getLabStatusVariant делегируют в labStatusConfig.
export function formatLabStatus(status) {
  return getLabStatusConfig(status).label;
}

export function getLabStatusVariant(status) {
  return getLabStatusConfig(status).variant;
}

export function formatPaymentStatus(status) {
  return _paymentStatusLabels[status] || status || 'Неизвестно';
}

export function formatSpecialtyLabel(specialty) {
  return _specialtyLabels[specialty] || specialty || 'Лаборатория';
}

export function formatSeverityLabel(severity) {
  return _severityLabels[severity] || severity || 'Без отклонений';
}
