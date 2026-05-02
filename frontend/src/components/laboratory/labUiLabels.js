const statusLabels = {
  waiting: 'Ожидает',
  confirmed: 'Подтверждён',
  pending: 'Ожидает',
  called: 'Вызван',
  in_progress: 'В работе',
  completed: 'Завершён',
  done: 'Завершён',
  DRAFT: 'Черновик',
  IN_PROGRESS: 'Заполняется',
  READY: 'Готов',
  FINALIZED: 'Финализирован',
  PRINTED: 'Напечатан'
};

const paymentStatusLabels = {
  pending: 'Не оплачено',
  paid: 'Оплачено',
  partial: 'Частично оплачено',
  refunded: 'Возврат',
  cancelled: 'Отменено'
};

const specialtyLabels = {
  lab: 'Лаборатория',
  laboratory: 'Лаборатория',
  general: 'Общая очередь'
};

const severityLabels = {
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
  return statusLabels[status] || status || 'Неизвестно';
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
  return paymentStatusLabels[status] || status || 'Неизвестно';
}

export function formatSpecialtyLabel(specialty) {
  return specialtyLabels[specialty] || specialty || 'Лаборатория';
}

export function formatSeverityLabel(severity) {
  return severityLabels[severity] || severity || 'Без отклонений';
}
