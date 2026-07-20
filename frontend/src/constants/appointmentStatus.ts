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
// Получение прогресса в потоке (0-100%)
export const getProgress = (status) => {
  const index = STATUS_FLOW.indexOf(status);
  return index >= 0 ? (index / (STATUS_FLOW.length - 1)) * 100 : 0;
};
