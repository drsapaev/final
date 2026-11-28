/**
 * Lab UI labels with Russian fallbacks for callers without a translator.
 *
 * L-H-3 fix: маппинг статусов делегирован в utils/labStatusConfig.js.
 *
 * Usage in components:
 *   import { formatLabStatus, getLabStatusVariant } from './labUiLabels';
 *
 *   // Для stepper / step-index используйте labStatusConfig напрямую:
 *   import { getLabStatusConfig, getLabReportStepIndex } from './utils/labStatusConfig';
 */

import { formatLabStatusLabel, getLabStatusConfig, type LabStatusTranslator } from './utils/labStatusConfig';

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
export function formatLabStatus(status: string, translate?: LabStatusTranslator) {
  return formatLabStatusLabel(status, translate);
}

export function getLabStatusVariant(status: string) {
  return getLabStatusConfig(status).variant;
}

export function formatPaymentStatus(status: string) {
  return _paymentStatusLabels[status as keyof typeof _paymentStatusLabels] || status || 'Неизвестно';
}

export function formatSpecialtyLabel(specialty: string) {
  return _specialtyLabels[specialty as keyof typeof _specialtyLabels] || specialty || 'Лаборатория';
}

export function formatSeverityLabel(severity: string) {
  return _severityLabels[severity as keyof typeof _severityLabels] || severity || 'Без отклонений';
}
