/**
 * QueueManagementCard - Универсальный компонент управления очередью
 * Кнопки для управления статусами записей во всех специализированных панелях
 */
import { useState } from 'react';
import PropTypes from 'prop-types';
import {

  XCircle,
  RotateCcw,
  Stethoscope,
  CheckCircle,
  AlertCircle,
  Clock,
  Bell } from
'lucide-react';
import api from '../../services/api';
import logger from '../../utils/logger';

const normalizeQueueAction = (action) => String(action || '').trim().toLowerCase().replace(/-/g, '_');

const QUEUE_ACTION_ALIASES = {
  no_show: ['no_show'],
  restore_next: ['restore_next'],
  send_to_diagnostics: ['send_to_diagnostics', 'diagnostics'],
  notify_diagnostics_return: ['notify_diagnostics_return', 'call_from_diagnostics'],
  incomplete: ['incomplete'],
  complete: ['complete']
};

const QUEUE_COMPLETED_STATUSES = new Set(['served', 'completed', 'done']);
const QUEUE_INCOMPLETE_STATUSES = new Set(['incomplete']);
const QUEUE_CANCELLED_STATUSES = new Set(['cancelled']);

const hasBackendQueueAction = (entry, action, flagName) => {
  if (entry?.[flagName] === true) {
    return true;
  }

  if (!Array.isArray(entry?.available_actions)) {
    return false;
  }

  const availableActions = new Set(entry.available_actions.map(normalizeQueueAction));
  const aliases = QUEUE_ACTION_ALIASES[action] || [action];
  return aliases.some((alias) => availableActions.has(normalizeQueueAction(alias)));
};

/**
 * Кнопки действий для одной записи в очереди
 * @param {object} entry - Запись из очереди (appointment/queue entry)
 * @param {function} onStatusChange - Callback после изменения статуса
 * @param {object} styles - Объект со стилями кнопок (actionButtonStyle, colors)
 */
export const QueueActionButtons = ({
  entry,
  onStatusChange,
  styles = {},
  compact = false
}) => {
  const [loading, setLoading] = useState(false);

  const {
    actionButtonStyle = {
      padding: '6px',
      borderRadius: '6px',
      border: 'none',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      marginRight: '4px'
    },
    dangerColor = 'var(--mac-error)',
    successColor = 'var(--mac-success)',
    warningColor = 'var(--mac-warning)',
    infoColor = 'var(--mac-accent-blue)',
    getColor = (color, shade) => {
      const colors = {
        danger: { 100: 'var(--mac-error-bg)', 500: 'var(--mac-error)' },
        success: { 100: 'var(--mac-success-bg)', 500: 'var(--mac-success)' },
        warning: { 100: 'var(--mac-warning-bg)', 500: 'var(--mac-warning)' },
        info: { 100: 'var(--mac-accent-bg)', 500: 'var(--mac-accent-blue)' }
      };
      return colors[color]?.[shade] || '#666';
    }
  } = styles;

  const entryId = entry?.queue_entry_id ?? null;
  const status = entry.queue_status || entry.status || null;

  if (!entryId) {
    logger.warn('[QueueActionButtons] Missing queue_entry_id, skipping queue action controls', {
      entry,
      status
    });
    return null;
  }

  const handleAction = async (action, payload = {}) => {
    if (loading) return;
    setLoading(true);

    try {
      let response;
      switch (action) {
        case 'no-show':
          response = await api.post(`/queue/entry/${entryId}/no-show`);
          break;
        case 'restore-next':
          response = await api.post(`/queue/entry/${entryId}/restore-next`, payload);
          break;
        case 'diagnostics':
          response = await api.post(`/queue/entry/${entryId}/diagnostics`);
          break;
        case 'call-from-diagnostics':
          // Используем endpoint для возврата с діагностики
          response = await api.post(`/queue/position/notify/diagnostics-return/${entryId}`);
          break;
        case 'incomplete':
          response = await api.post(`/queue/entry/${entryId}/incomplete`, payload);
          break;
        case 'complete':
          response = await api.post(`/doctor/queue/${entryId}/complete`);
          break;
        default:
          throw new Error(`Unknown action: ${action}`);
      }

      logger.info(`[QueueActionButtons] ${action} success for entry ${entryId}`, response?.data);

      if (onStatusChange) {
        onStatusChange(action, entry, response?.data);
      }
    } catch (err) {
      logger.error(`[QueueActionButtons] ${action} failed for entry ${entryId}:`, err);
      // Можно добавить toast notification здесь
    } finally {
      setLoading(false);
    }
  };

  const iconSize = compact ? 14 : 16;

  // Кнопки в зависимости от статуса
  const renderButtons = () => {
    const buttons = [];

    if (hasBackendQueueAction(entry, 'no_show', 'can_no_show')) {
      buttons.push(
        <button
          key="no-show"
          style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
          onClick={() => handleAction('no-show')}
          disabled={loading}
          aria-label="Отметить неявку"
          title="Отметить неявку">

                    <XCircle size={iconSize} />
                </button>);
    }

    if (hasBackendQueueAction(entry, 'send_to_diagnostics', 'can_send_to_diagnostics')) {
      buttons.push(
        <button
          key="diagnostics"
          style={{ ...actionButtonStyle, background: getColor('info', 100), color: infoColor }}
          onClick={() => handleAction('diagnostics')}
          disabled={loading}
          aria-label="Направить на обследование"
          title="На обследование">

                    <Stethoscope size={iconSize} />
                </button>);
    }

    if (hasBackendQueueAction(entry, 'notify_diagnostics_return', 'can_notify_diagnostics_return')) {
      buttons.push(
        <button
          key="call-from-diagnostics"
          style={{ ...actionButtonStyle, background: getColor('info', 100), color: infoColor }}
          onClick={() => handleAction('call-from-diagnostics')}
          disabled={loading}
          aria-label="Вернуть с диагностики и вызвать повторно"
          title="Вернуть с диагностики (Вызвать повторно)">

                    <Bell size={iconSize} />
                </button>);
    }

    if (hasBackendQueueAction(entry, 'complete', 'can_complete')) {
      buttons.push(
        <button
          key="complete"
          style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
          onClick={() => handleAction('complete')}
          disabled={loading}
          aria-label="Завершить приём"
          title="Завершить приём">

                    <CheckCircle size={iconSize} />
                </button>);
    }

    if (hasBackendQueueAction(entry, 'incomplete', 'can_incomplete')) {
      buttons.push(
        <button
          key="incomplete"
          style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
          onClick={() => handleAction('incomplete', { reason: 'Не вернулся с обследования' })}
          disabled={loading}
          aria-label="Отметить, что пациент не вернулся"
          title="Не вернулся">

                    <AlertCircle size={iconSize} />
                </button>);
    }

    if (hasBackendQueueAction(entry, 'restore_next', 'can_restore_next')) {
      buttons.push(
        <button
          key="restore-next"
          style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
          onClick={() => handleAction('restore-next')}
          disabled={loading}
          aria-label="Восстановить пациента следующим в очереди"
          title="Восстановить следующим">

                    <RotateCcw size={iconSize} />
                </button>);
    }

    if (buttons.length > 0) {
      return <>{buttons}</>;
    }

    if (
      !QUEUE_COMPLETED_STATUSES.has(status) &&
      !QUEUE_INCOMPLETE_STATUSES.has(status) &&
      !QUEUE_CANCELLED_STATUSES.has(status)
    ) {
      return null;
    }

    switch (status) {
      case 'waiting':
        return (
          <button
            style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
            onClick={() => handleAction('no-show')}
            disabled={loading}
            aria-label="Отметить неявку"
            title="Отметить неявку">
            
                        <XCircle size={iconSize} />
                    </button>);


      case 'called':
      case 'calling':
      case 'in_cabinet':
        return (
          <>
                        <button
              style={{ ...actionButtonStyle, background: getColor('info', 100), color: infoColor }}
              onClick={() => handleAction('diagnostics')}
              disabled={loading}
              aria-label="Направить на обследование"
              title="На обследование">
              
                            <Stethoscope size={iconSize} />
                        </button>
                        <button
              style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
              onClick={() => handleAction('complete')}
              disabled={loading}
              aria-label="Завершить приём"
              title="Завершить приём">
              
                            <CheckCircle size={iconSize} />
                        </button>
                        <button
              style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
              onClick={() => handleAction('no-show')}
              disabled={loading}
              aria-label="Отметить, что пациент не явился"
              title="Не явился">
              
                            <XCircle size={iconSize} />
                        </button>
                    </>);


      case 'diagnostics':
        return (
          <>
                        <button
              style={{ ...actionButtonStyle, background: getColor('info', 100), color: infoColor }}
              onClick={() => handleAction('call-from-diagnostics')}
              disabled={loading}
              aria-label="Вернуть с диагностики и вызвать повторно"
              title="Вернуть с диагностики (Вызвать повторно)">
              
                            <Bell size={iconSize} />
                        </button>
                        <button
              style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
              onClick={() => handleAction('complete')}
              disabled={loading}
              aria-label="Завершить приём"
              title="Завершить приём">
              
                            <CheckCircle size={iconSize} />
                        </button>
                        <button
              style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
              onClick={() => handleAction('incomplete', { reason: 'Не вернулся с обследования' })}
              disabled={loading}
              aria-label="Отметить, что пациент не вернулся"
              title="Не вернулся">
              
                            <AlertCircle size={iconSize} />
                        </button>
                    </>);


      case 'no_show':
        return (
          <button
            style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
            onClick={() => handleAction('restore-next')}
            disabled={loading}
            aria-label="Восстановить пациента следующим в очереди"
            title="Восстановить следующим">
            
                        <RotateCcw size={iconSize} />
                    </button>);


      case 'served':
      case 'completed':
      case 'done':
        return (
          <span style={{ color: successColor, fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle size={14} /> Завершён
                    </span>);


      case 'incomplete':
        return (
          <span style={{ color: dangerColor, fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <AlertCircle size={14} /> Не завершён
                    </span>);


      case 'cancelled':
        return (
          <span style={{ color: 'var(--mac-text-secondary)', fontSize: '12px' }}>Отменён</span>);


      default:
        return null;
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
            {loading ?
      <Clock size={iconSize} style={{ animation: 'spin 1s linear infinite' }} /> :

      renderButtons()
      }
        </div>);

};

/**
 * Карточка статистики очереди (для хедера)
 */
export const QueueStatsBar = ({ stats, getColor }) => {
  const defaultGetColor = (color, shade) => {
    const colors = {
      warning: { 500: 'var(--mac-warning)' },
      primary: { 500: 'var(--mac-accent-blue)' },
      success: { 500: 'var(--mac-success)' }
    };
    return colors[color]?.[shade] || '#666';
  };

  const gc = getColor || defaultGetColor;

  return (
    <div style={{ display: 'flex', gap: '12px', fontSize: '14px' }}>
            <span style={{
        background: `${gc('warning', 500)}20`,
        color: gc('warning', 500),
        padding: '4px 8px',
        borderRadius: '6px'
      }}>
                Ожидают: {stats?.waiting || 0}
            </span>
            <span style={{
        background: `${gc('primary', 500)}20`,
        color: gc('primary', 500),
        padding: '4px 8px',
        borderRadius: '6px'
      }}>
                Вызваны: {stats?.called || 0}
            </span>
            <span style={{
        background: `${gc('success', 500)}20`,
        color: gc('success', 500),
        padding: '4px 8px',
        borderRadius: '6px'
      }}>
                Обслужены: {stats?.served || 0}
            </span>
        </div>);

};

/**
 * Хелпер для маппинга статусов очереди
 */
export const getQueueStatusInfo = (status) => {
  const statusMap = {
    waiting: { label: 'Ожидает', variant: 'warning', color: 'var(--mac-warning)' },
    called: { label: 'Вызван', variant: 'primary', color: 'var(--mac-accent-blue)' },
    calling: { label: 'Вызывается', variant: 'primary', color: 'var(--mac-accent-blue)' },
    in_cabinet: { label: 'В кабинете', variant: 'info', color: '#06b6d4' },
    in_service: { label: 'На приёме', variant: 'info', color: '#06b6d4' },
    diagnostics: { label: 'На обследовании', variant: 'info', color: 'var(--mac-accent-purple)' },
    served: { label: 'Обслужен', variant: 'success', color: 'var(--mac-success)' },
    completed: { label: 'Завершён', variant: 'success', color: 'var(--mac-success)' },
    done: { label: 'Завершён', variant: 'success', color: 'var(--mac-success)' },
    incomplete: { label: 'Не завершён', variant: 'danger', color: 'var(--mac-error)' },
    no_show: { label: 'Не явился', variant: 'danger', color: 'var(--mac-error)' },
    cancelled: { label: 'Отменён', variant: 'secondary', color: 'var(--mac-text-secondary)' }
  };

  return statusMap[status] || { label: status, variant: 'default', color: 'var(--mac-text-secondary)' };
};

const queueEntryShape = PropTypes.shape({
  queue_entry_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  status: PropTypes.string,
  queue_status: PropTypes.string
});

const styleConfigShape = PropTypes.shape({
  actionButtonStyle: PropTypes.object,
  dangerColor: PropTypes.string,
  successColor: PropTypes.string,
  warningColor: PropTypes.string,
  infoColor: PropTypes.string,
  getColor: PropTypes.func
});

QueueActionButtons.propTypes = {
  entry: queueEntryShape,
  onStatusChange: PropTypes.func,
  styles: styleConfigShape,
  compact: PropTypes.bool
};

QueueStatsBar.propTypes = {
  stats: PropTypes.shape({
    waiting: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    called: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    served: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
  }),
  getColor: PropTypes.func
};

export default QueueActionButtons;
