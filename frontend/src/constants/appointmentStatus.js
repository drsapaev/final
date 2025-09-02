// Статусы записей - жесткий поток: запись → платеж → прием → медкарта → рецепт
export const APPOINTMENT_STATUS = {
  PENDING: 'pending',      // Запись создана, ожидает оплаты
  PAID: 'paid',           // Оплачено, можно отправлять к врачу
  IN_VISIT: 'in_visit',   // Прием у врача в процессе
  COMPLETED: 'completed', // Прием завершен (EMR + рецепт готовы)
  CANCELLED: 'cancelled', // Отменено
  NO_SHOW: 'no_show'      // Пациент не явился
};

// Порядок статусов для валидации переходов
export const STATUS_FLOW = [
  APPOINTMENT_STATUS.PENDING,
  APPOINTMENT_STATUS.PAID,
  APPOINTMENT_STATUS.IN_VISIT,
  APPOINTMENT_STATUS.COMPLETED
];

// Цвета статусов для UI
export const STATUS_COLORS = {
  [APPOINTMENT_STATUS.PENDING]: 'warning',
  [APPOINTMENT_STATUS.PAID]: 'success',
  [APPOINTMENT_STATUS.IN_VISIT]: 'info',
  [APPOINTMENT_STATUS.COMPLETED]: 'success',
  [APPOINTMENT_STATUS.CANCELLED]: 'danger',
  [APPOINTMENT_STATUS.NO_SHOW]: 'secondary'
};

// Тексты статусов на русском
export const STATUS_LABELS = {
  [APPOINTMENT_STATUS.PENDING]: 'Ожидает оплаты',
  [APPOINTMENT_STATUS.PAID]: 'Оплачено',
  [APPOINTMENT_STATUS.IN_VISIT]: 'На приеме',
  [APPOINTMENT_STATUS.COMPLETED]: 'Завершено',
  [APPOINTMENT_STATUS.CANCELLED]: 'Отменено',
  [APPOINTMENT_STATUS.NO_SHOW]: 'Не явился'
};

// Иконки статусов
export const STATUS_ICONS = {
  [APPOINTMENT_STATUS.PENDING]: '⏳',
  [APPOINTMENT_STATUS.PAID]: '✅',
  [APPOINTMENT_STATUS.IN_VISIT]: '👨‍⚕️',
  [APPOINTMENT_STATUS.COMPLETED]: '✅',
  [APPOINTMENT_STATUS.CANCELLED]: '❌',
  [APPOINTMENT_STATUS.NO_SHOW]: '🚫'
};

// Проверка возможности перехода между статусами
export const canTransitionTo = (fromStatus, toStatus) => {
  const fromIndex = STATUS_FLOW.indexOf(fromStatus);
  const toIndex = STATUS_FLOW.indexOf(toStatus);
  
  // Можно переходить только вперед по потоку или к отмене/неявке
  if (toStatus === APPOINTMENT_STATUS.CANCELLED || toStatus === APPOINTMENT_STATUS.NO_SHOW) {
    return fromStatus !== APPOINTMENT_STATUS.COMPLETED;
  }
  
  return toIndex === fromIndex + 1;
};

// Получение следующего статуса в потоке
export const getNextStatus = (currentStatus) => {
  const currentIndex = STATUS_FLOW.indexOf(currentStatus);
  return currentIndex < STATUS_FLOW.length - 1 ? STATUS_FLOW[currentIndex + 1] : null;
};

// Получение предыдущего статуса в потоке
export const getPreviousStatus = (currentStatus) => {
  const currentIndex = STATUS_FLOW.indexOf(currentStatus);
  return currentIndex > 0 ? STATUS_FLOW[currentIndex - 1] : null;
};

// Проверка, можно ли начать прием (статус PAID)
export const canStartVisit = (status) => {
  return status === APPOINTMENT_STATUS.PAID;
};

// Проверка, можно ли завершить прием (есть EMR)
export const canCompleteVisit = (status, hasEMR) => {
  return status === APPOINTMENT_STATUS.IN_VISIT && hasEMR;
};

// Проверка, можно ли создать рецепт (есть EMR)
export const canCreatePrescription = (status, hasEMR) => {
  return (status === APPOINTMENT_STATUS.IN_VISIT || status === APPOINTMENT_STATUS.COMPLETED) && hasEMR;
};

// Проверка, можно ли отменить запись
export const canCancel = (status) => {
  return status !== APPOINTMENT_STATUS.COMPLETED;
};

// Получение прогресса в потоке (0-100%)
export const getProgress = (status) => {
  const index = STATUS_FLOW.indexOf(status);
  return index >= 0 ? (index / (STATUS_FLOW.length - 1)) * 100 : 0;
};
