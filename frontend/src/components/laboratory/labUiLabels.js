/**
 * Lab UI labels — PR-73: now locale-aware via useTranslation.
 *
 * L-H-3 fix: маппинг статусов делегирован в utils/labStatusConfig.js.
 * Этот модуль теперь содержит только i18n-обёртки и payment/specialty
 * labels (которые пока не мигрированы в shared config).
 *
 * Usage in components:
 *   const { t } = useTranslation();
 *   const labels = getLabLabels(t);
 *   labels.status('waiting')  // → 'Ожидает' / 'Kutmoqda' / 'Waiting'
 *
 *   // Для badge-variant и stepper используйте labStatusConfig напрямую:
 *   import { getLabStatusConfig, getLabReportStepIndex } from './utils/labStatusConfig';
 */

import {
  LAB_REPORT_STATUS_CONFIG,
  LAB_QUEUE_STATUS_CONFIG,
  getLabStatusConfig,
} from './utils/labStatusConfig';

export function getLabLabels(t) {
  // L-H-3 fix: читаем из единого источника истины.
  const statusLabels = {
    ...Object.fromEntries(
      Object.entries(LAB_QUEUE_STATUS_CONFIG).map(([key, cfg]) => [key, cfg.label])
    ),
    ...Object.fromEntries(
      LAB_REPORT_STATUS_CONFIG.map((cfg) => [cfg.key, cfg.label])
    ),
  };

  const paymentStatusLabels = {
    pending: t('labPaymentPending'),
    paid: t('labPaymentPaid'),
    partial: t('labPaymentPartial'),
    refunded: t('labPaymentRefunded'),
    cancelled: t('labPaymentCancelled')
  };

  const specialtyLabels = {
    lab: t('labSpecialtyLab'),
    laboratory: t('labSpecialtyLab'),
    general: t('labSpecialtyGeneral')
  };

  const severityLabels = {
    critical: t('labSeverityCritical'),
    flagged: t('labSeverityFlagged'),
    warning: t('labSeverityWarning'),
    clean: t('labSeverityClean')
  };

  const signerFieldLabels = {
    lab_technician_label: t('labTechnicianLabel'),
    lab_technician_name: t('labTechnicianName'),
    approver_label: t('labApproverLabel'),
    approver_name: t('labApproverName')
  };

  return {
    statusLabels,
    paymentStatusLabels,
    specialtyLabels,
    severityLabels,
    signerFieldLabels,
    formatLabStatus: (status) => getLabStatusConfig(status).label,
    formatPaymentStatus: (status) => paymentStatusLabels[status] || status || t('labUnknown'),
    formatSpecialtyLabel: (specialty) => specialtyLabels[specialty] || specialty || t('labSpecialtyLab'),
    formatSeverityLabel: (severity) => severityLabels[severity] || severity || t('labSeverityClean'),
  };
}

// Legacy static exports for backward compatibility (hardcoded Russian).
// L-H-3 fix: label/variant берутся из labStatusConfig.js — единый источник.
// Оставлены только payment/specialty/severity — они не входят в status-config
// (относятся к разным доменам: оплата, специализация, severity-флаги).

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
