/**
 * Lab UI labels — PR-73: now locale-aware via useTranslation.
 *
 * Usage in components:
 *   const { t } = useTranslation();
 *   const labels = getLabLabels(t);
 *   labels.status('waiting')  // → 'Ожидает' / 'Kutmoqda' / 'Waiting'
 */

export function getLabLabels(t) {
  const statusLabels = {
    waiting: t('labWaiting'),
    confirmed: t('labConfirmed'),
    pending: t('labWaiting'),
    called: t('labCalled'),
    in_progress: t('labInProgress'),
    completed: t('labCompleted'),
    done: t('labCompleted'),
    DRAFT: t('labDraft'),
    IN_PROGRESS: t('labFilling'),
    READY: t('labReady'),
    FINALIZED: t('labFinalized'),
    PRINTED: t('labPrinted')
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
    formatLabStatus: (status) => statusLabels[status] || status || t('labUnknown'),
    formatPaymentStatus: (status) => paymentStatusLabels[status] || status || t('labUnknown'),
    formatSpecialtyLabel: (specialty) => specialtyLabels[specialty] || specialty || t('labSpecialtyLab'),
    formatSeverityLabel: (severity) => severityLabels[severity] || severity || t('labSeverityClean'),
  };
}

// Legacy static exports for backward compatibility (hardcoded Russian)
const _statusLabels = {
  waiting: 'Ожидает',
  confirmed: 'Подтверждён',
  pending: 'Ожидает',
  called: 'Вызван',
  in_progress: 'В работе',
  completed: 'Завершён',
  done: 'Завершён',
  DRAFT: 'Черновик',
  IN_PROGRESS: 'Заполняется',
  READY: 'Готов к проверке',
  FINALIZED: 'Утверждён',
  PRINTED: 'Напечатан'
};

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

export function formatLabStatus(status) {
  return _statusLabels[status] || status || 'Неизвестно';
}

export function getLabStatusVariant(status) {
  if (status === 'FINALIZED' || status === 'PRINTED' || status === 'completed' || status === 'done') {
    return 'success';
  }
  if (status === 'READY' || status === 'called' || status === 'in_progress' || status === 'IN_PROGRESS') {
    return 'primary';
  }
  return 'warning';
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
