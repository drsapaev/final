
/**
 * QueueManagementCard - Универсальный компонент управления очередью
 * Кнопки для управления статусами записей во всех специализированных панелях
 *
 * UX Audit Registrar #3: все inline-стили перенесены в QueueManagementCard.css.
 * Backward compat: props.styles (actionButtonStyle, getColor) всё ещё поддерживается,
 * но если не передан — используются CSS-классы с macos design tokens.
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
import './QueueManagementCard.css';
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

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
 * Renders a single action button.
 * UX Audit Registrar #3: использует CSS-классы вместо inline-стилей.
 * Если передан styles.actionButtonStyle — используется он (backward compat),
 * иначе — CSS-класс .qm-action-btn.qm-action-btn--{color}.
 */
const ActionButton = ({ color, icon: Icon, iconSize, onClick, disabled, ariaLabel, title, actionButtonStyle, getColor }: Record<string, any>) => {
  // Backward compat: если передан custom actionButtonStyle — используем inline-стиль.
  if (actionButtonStyle) {
    return (
      <button
        style={{
          ...actionButtonStyle,
          background: getColor ? getColor(color, 100) : undefined,
          color: getColor ? getColor(color, 500) : undefined,
        }}
        onClick={onClick}
        disabled={disabled}
        aria-label={ariaLabel}
        title={title}>
        <Icon size={iconSize} />
      </button>
    );
  }

  // Default: CSS-класс с macos tokens.
  return (
    <button
      className={`qm-action-btn qm-action-btn--${color}`}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      title={title}>
      <Icon size={iconSize} />
    </button>
  );
};

ActionButton.propTypes = {
  color: PropTypes.oneOf(['danger', 'info', 'success', 'warning']).isRequired,
  icon: PropTypes.elementType.isRequired,
  iconSize: PropTypes.number.isRequired,
  onClick: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  ariaLabel: PropTypes.string,
  title: PropTypes.string,
  actionButtonStyle: PropTypes.object,
  getColor: PropTypes.func,
};

/**
 * Кнопки действий для одной записи в очереди
 * @param {object} entry - Запись из очереди (appointment/queue entry)
 * @param {function} onStatusChange - Callback после изменения статуса
 * @param {object} styles - Объект со стилями кнопок (actionButtonStyle, colors) — optional, для backward compat
 */
export const QueueActionButtons = ({
  entry,
  onStatusChange,
  styles: stylesRaw = {},
  compact = false
}) => {
  const styles = stylesRaw as Record<string, any>;
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [loading, setLoading] = useState(false);

  const {
    actionButtonStyle = null, // UX Audit Registrar #3: по умолчанию null — используем CSS-классы
    getColor = null,
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
          response = await api.post(`/queue/entry/${entryId}/no-show`, undefined);
          break;
        case 'restore-next':
          response = await api.post(`/queue/entry/${entryId}/restore-next`, payload);
          break;
        case 'diagnostics':
          response = await api.post(`/queue/entry/${entryId}/diagnostics`, undefined);
          break;
        case 'call-from-diagnostics':
          // Используем endpoint для возврата с діагностики
          response = await api.post(`/queue/position/notify/diagnostics-return/${entryId}`, undefined);
          break;
        case 'incomplete':
          response = await api.post(`/queue/entry/${entryId}/incomplete`, payload);
          break;
        case 'complete':
          response = await api.post(`/doctor/queue/${entryId}/complete`, undefined);
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

  // Common props для всех кнопок
  const btnProps = { iconSize, actionButtonStyle, getColor, disabled: loading };

  // Кнопки в зависимости от статуса
  const renderButtons = () => {
    const buttons = [];

    if (hasBackendQueueAction(entry, 'no_show', 'can_no_show')) {
      buttons.push(
        <ActionButton
          key="no-show"
          color="danger"
          icon={XCircle}
          onClick={() => handleAction('no-show')}
          ariaLabel={t('misc.qmc_mark_no_show')}
          title={t('misc.qmc_mark_no_show')}
          {...btnProps} />
      );
    }

    if (hasBackendQueueAction(entry, 'send_to_diagnostics', 'can_send_to_diagnostics')) {
      buttons.push(
        <ActionButton
          key="diagnostics"
          color="info"
          icon={Stethoscope}
          onClick={() => handleAction('diagnostics')}
          ariaLabel={t('misc.qmc_send_to_diagnostics_aria')}
          title={t('misc.qmc_to_diagnostics')}
          {...btnProps} />
      );
    }

    if (hasBackendQueueAction(entry, 'notify_diagnostics_return', 'can_notify_diagnostics_return')) {
      buttons.push(
        <ActionButton
          key="call-from-diagnostics"
          color="info"
          icon={Bell}
          onClick={() => handleAction('call-from-diagnostics')}
          ariaLabel={t('misc.qmc_return_from_diagnostics_aria')}
          title={t('misc.qmc_return_from_diagnostics_title')}
          {...btnProps} />
      );
    }

    if (hasBackendQueueAction(entry, 'complete', 'can_complete')) {
      buttons.push(
        <ActionButton
          key="complete"
          color="success"
          icon={CheckCircle}
          onClick={() => handleAction('complete')}
          ariaLabel={t('misc.qmc_complete_visit')}
          title={t('misc.qmc_complete_visit')}
          {...btnProps} />
      );
    }

    if (hasBackendQueueAction(entry, 'incomplete', 'can_incomplete')) {
      buttons.push(
        <ActionButton
          key="incomplete"
          color="warning"
          icon={AlertCircle}
          onClick={() => handleAction('incomplete', { reason: t('misc.qmc_not_returned_from_diagnostics') })}
          ariaLabel={t('misc.qmc_mark_not_returned')}
          title={t('misc.qmc_not_returned')}
          {...btnProps} />
      );
    }

    if (hasBackendQueueAction(entry, 'restore_next', 'can_restore_next')) {
      buttons.push(
        <ActionButton
          key="restore-next"
          color="warning"
          icon={RotateCcw}
          onClick={() => handleAction('restore-next')}
          ariaLabel={t('misc.qmc_restore_next_aria')}
          title={t('misc.qmc_restore_next')}
          {...btnProps} />
      );
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
          <ActionButton
            color="danger"
            icon={XCircle}
            onClick={() => handleAction('no-show')}
            ariaLabel={t('misc.qmc_mark_no_show')}
            title={t('misc.qmc_mark_no_show')}
            {...btnProps} />
        );

      case 'called':
      case 'calling':
      case 'in_cabinet':
        return (
          <>
            <ActionButton
              color="info"
              icon={Stethoscope}
              onClick={() => handleAction('diagnostics')}
              ariaLabel={t('misc.qmc_send_to_diagnostics_aria')}
              title={t('misc.qmc_to_diagnostics')}
              {...btnProps} />
            <ActionButton
              color="success"
              icon={CheckCircle}
              onClick={() => handleAction('complete')}
              ariaLabel={t('misc.qmc_complete_visit')}
              title={t('misc.qmc_complete_visit')}
              {...btnProps} />
            <ActionButton
              color="danger"
              icon={XCircle}
              onClick={() => handleAction('no-show')}
              ariaLabel={t('misc.qmc_mark_patient_no_show')}
              title={t('misc.qmc_not_arrived')}
              {...btnProps} />
          </>
        );

      case 'diagnostics':
        return (
          <>
            <ActionButton
              color="info"
              icon={Bell}
              onClick={() => handleAction('call-from-diagnostics')}
              ariaLabel={t('misc.qmc_return_from_diagnostics_aria')}
              title={t('misc.qmc_return_from_diagnostics_title')}
              {...btnProps} />
            <ActionButton
              color="success"
              icon={CheckCircle}
              onClick={() => handleAction('complete')}
              ariaLabel={t('misc.qmc_complete_visit')}
              title={t('misc.qmc_complete_visit')}
              {...btnProps} />
            <ActionButton
              color="warning"
              icon={AlertCircle}
              onClick={() => handleAction('incomplete', { reason: t('misc.qmc_not_returned_from_diagnostics') })}
              ariaLabel={t('misc.qmc_mark_not_returned')}
              title={t('misc.qmc_not_returned')}
              {...btnProps} />
          </>
        );

      case 'no_show':
        return (
          <ActionButton
            color="warning"
            icon={RotateCcw}
            onClick={() => handleAction('restore-next')}
            ariaLabel={t('misc.qmc_restore_next_aria')}
            title={t('misc.qmc_restore_next')}
            {...btnProps} />
        );

      case 'served':
      case 'completed':
      case 'done':
        return (
          <span className="qm-status-text qm-status-text--success">
            <CheckCircle size={14 as unknown as "small" | "default" | "large" | "xlarge"} /> {t('misc.qmc_status_completed')}
          </span>
        );

      case 'incomplete':
        return (
          <span className="qm-status-text qm-status-text--danger">
            <AlertCircle size={14 as unknown as "small" | "default" | "large" | "xlarge"} /> {t('misc.qmc_status_incomplete')}
          </span>
        );

      case 'cancelled':
        return (
          <span className="qm-status-text qm-status-text--secondary">{t('misc.qmc_status_cancelled')}</span>
        );

      default:
        return null;
    }
  };

  return (
    <div className="qm-actions-container">
      {loading ?
        <Clock size={iconSize} className="qm-loading-icon" /> :
        renderButtons()
      }
    </div>
  );
};

/**
 * Карточка статистики очереди (для хедера)
 */
export const QueueStatsBar = ({ stats, getColor }: Record<string, any>) => {
  const styles = {} as Record<string, any> as Record<string, any>;
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // UX Audit Registrar #3: если getColor не передан — используем CSS-классы.
  // Backward compat: если getColor передан — используем inline-стили.
  if (getColor) {
    return (
      <div className="qm-stats-bar">
        <span style={{
          background: `${getColor('warning', 500)}20`,
          color: getColor('warning', 500),
          padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
          borderRadius: 'var(--mac-radius-sm)'
        }}>
          {t('misc.qmc_stats_waiting', { count: stats?.waiting || 0 })}
        </span>
        <span style={{
          background: `${getColor('primary', 500)}20`,
          color: getColor('primary', 500),
          padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
          borderRadius: 'var(--mac-radius-sm)'
        }}>
          {t('misc.qmc_stats_called', { count: stats?.called || 0 })}
        </span>
        <span style={{
          background: `${getColor('success', 500)}20`,
          color: getColor('success', 500),
          padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
          borderRadius: 'var(--mac-radius-sm)'
        }}>
          {t('misc.qmc_stats_served', { count: stats?.served || 0 })}
        </span>
      </div>
    );
  }

  // Default: CSS-классы с macos tokens.
  return (
    <div className="qm-stats-bar">
      <span className="qm-stats-pill qm-stats-pill--warning">
        {t('misc.qmc_stats_waiting', { count: stats?.waiting || 0 })}
      </span>
      <span className="qm-stats-pill qm-stats-pill--primary">
        {t('misc.qmc_stats_called', { count: stats?.called || 0 })}
      </span>
      <span className="qm-stats-pill qm-stats-pill--success">
        {t('misc.qmc_stats_served', { count: stats?.served || 0 })}
      </span>
    </div>
  );
};

/**
 * Хелпер для маппинга статусов очереди
 */
export const getQueueStatusInfo = (status) => {
  const statusMap = {
    waiting: { label: t18('misc.qmc_status_waiting'), variant: 'warning', color: 'var(--mac-warning)' },
    called: { label: t18('misc.qmc_status_called'), variant: 'primary', color: 'var(--mac-accent-blue)' },
    calling: { label: t18('misc.qmc_status_calling'), variant: 'primary', color: 'var(--mac-accent-blue)' },
    in_cabinet: { label: t18('misc.qmc_status_in_cabinet'), variant: 'info', color: 'var(--mac-accent-blue)' },
    in_service: { label: t18('misc.qmc_status_in_service'), variant: 'info', color: 'var(--mac-accent-blue)' },
    diagnostics: { label: t18('misc.qmc_status_diagnostics'), variant: 'info', color: 'var(--mac-accent-purple)' },
    served: { label: t18('misc.qmc_status_served'), variant: 'success', color: 'var(--mac-success)' },
    completed: { label: t18('misc.qmc_status_completed'), variant: 'success', color: 'var(--mac-success)' },
    done: { label: t18('misc.qmc_status_completed'), variant: 'success', color: 'var(--mac-success)' },
    incomplete: { label: t18('misc.qmc_status_incomplete'), variant: 'danger', color: 'var(--mac-error)' },
    no_show: { label: t18('misc.qmc_not_arrived'), variant: 'danger', color: 'var(--mac-error)' },
    cancelled: { label: t18('misc.qmc_status_cancelled'), variant: 'secondary', color: 'var(--mac-text-secondary)' }
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
