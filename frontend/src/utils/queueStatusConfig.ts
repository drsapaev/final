/**
 * Shared queue status configuration.
 *
 * UX Audit Doctor H-31: unified status colors/labels across DoctorPanel
 * and DoctorQueuePanel. Previously:
 * - DoctorPanel: waiting=warning, called=primary, in_service=info
 * - DoctorQueuePanel: waiting=info, called=warning, in_progress=primary
 *
 * Now: single source of truth for all queue status rendering.
 */

export const QUEUE_STATUS_CONFIG = {
  waiting: {
    label: 'Ожидает',
    variant: 'warning',
    color: 'warning',
  },
  called: {
    label: 'Вызван',
    variant: 'primary',
    color: 'primary',
  },
  in_service: {
    label: 'На приеме',
    variant: 'info',
    color: 'info',
  },
  in_progress: {
    label: 'На приеме',
    variant: 'info',
    color: 'info',
  },
  served: {
    label: 'Принят',
    variant: 'success',
    color: 'success',
  },
  completed: {
    label: 'Завершён',
    variant: 'success',
    color: 'success',
  },
  cancelled: {
    label: 'Отменён',
    variant: 'danger',
    color: 'danger',
  },
  no_show: {
    label: 'Не явился',
    variant: 'danger',
    color: 'danger',
  },
  incomplete: {
    label: 'Незавершён',
    variant: 'danger',
    color: 'danger',
  },
  diagnostics: {
    label: 'На диагностике',
    variant: 'info',
    color: 'info',
  },
};

/**
 * Get status variant for Badge component.
 * @param {string} status - queue status key
 * @returns {string} variant: 'warning' | 'primary' | 'info' | 'success' | 'danger' | 'default'
 */
export function getQueueStatusVariant(status) {
  return QUEUE_STATUS_CONFIG[status]?.variant || 'default';
}

/**
 * Get status label for display.
 * @param {string} status - queue status key
 * @returns {string} human-readable label
 */
export function getQueueStatusLabel(status) {
  return QUEUE_STATUS_CONFIG[status]?.label || status || '—';
}

export default QUEUE_STATUS_CONFIG;
