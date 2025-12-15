/**
 * QueueManagementCard - Универсальный компонент управления очередью
 * Кнопки для управления статусами записей во всех специализированных панелях
 */
import React, { useState } from 'react';
import {
    Phone,
    XCircle,
    RotateCcw,
    Stethoscope,
    CheckCircle,
    AlertCircle,
    Clock,
    Bell
} from 'lucide-react';
import api from '../../services/api';
import logger from '../../utils/logger';

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
        dangerColor = '#ef4444',
        successColor = '#22c55e',
        warningColor = '#f59e0b',
        infoColor = '#3b82f6',
        getColor = (color, shade) => {
            const colors = {
                danger: { 100: '#fee2e2', 500: '#ef4444' },
                success: { 100: '#dcfce7', 500: '#22c55e' },
                warning: { 100: '#fef3c7', 500: '#f59e0b' },
                info: { 100: '#dbeafe', 500: '#3b82f6' }
            };
            return colors[color]?.[shade] || '#666';
        }
    } = styles;

    const entryId = entry.queue_entry_id || entry.id;
    const status = entry.status || entry.queue_status || 'waiting';

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
                    response = await api.post(`/queue/entry/${entryId}/status`, null, {
                        params: { status: 'served' }
                    });
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
        switch (status) {
            case 'waiting':
                return (
                    <button
                        style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                        onClick={() => handleAction('no-show')}
                        disabled={loading}
                        title="Отметить неявку"
                    >
                        <XCircle size={iconSize} />
                    </button>
                );

            case 'called':
            case 'calling':
            case 'in_cabinet':
                return (
                    <>
                        <button
                            style={{ ...actionButtonStyle, background: getColor('info', 100), color: infoColor }}
                            onClick={() => handleAction('diagnostics')}
                            disabled={loading}
                            title="На обследование"
                        >
                            <Stethoscope size={iconSize} />
                        </button>
                        <button
                            style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                            onClick={() => handleAction('complete')}
                            disabled={loading}
                            title="Завершить приём"
                        >
                            <CheckCircle size={iconSize} />
                        </button>
                        <button
                            style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                            onClick={() => handleAction('no-show')}
                            disabled={loading}
                            title="Не явился"
                        >
                            <XCircle size={iconSize} />
                        </button>
                    </>
                );

            case 'diagnostics':
                return (
                    <>
                        <button
                            style={{ ...actionButtonStyle, background: getColor('info', 100), color: infoColor }}
                            onClick={() => handleAction('call-from-diagnostics')}
                            disabled={loading}
                            title="Вернуть с диагностики (Вызвать повторно)"
                        >
                            <Bell size={iconSize} />
                        </button>
                        <button
                            style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                            onClick={() => handleAction('complete')}
                            disabled={loading}
                            title="Завершить приём"
                        >
                            <CheckCircle size={iconSize} />
                        </button>
                        <button
                            style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
                            onClick={() => handleAction('incomplete', { reason: 'Не вернулся с обследования' })}
                            disabled={loading}
                            title="Не вернулся"
                        >
                            <AlertCircle size={iconSize} />
                        </button>
                    </>
                );

            case 'no_show':
                return (
                    <button
                        style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
                        onClick={() => handleAction('restore-next')}
                        disabled={loading}
                        title="Восстановить следующим"
                    >
                        <RotateCcw size={iconSize} />
                    </button>
                );

            case 'served':
            case 'completed':
            case 'done':
                return (
                    <span style={{ color: successColor, fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle size={14} /> Завершён
                    </span>
                );

            case 'incomplete':
                return (
                    <span style={{ color: dangerColor, fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <AlertCircle size={14} /> Не завершён
                    </span>
                );

            case 'cancelled':
                return (
                    <span style={{ color: '#6b7280', fontSize: '12px' }}>Отменён</span>
                );

            default:
                return null;
        }
    };

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
            {loading ? (
                <Clock size={iconSize} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
                renderButtons()
            )}
        </div>
    );
};

/**
 * Карточка статистики очереди (для хедера)
 */
export const QueueStatsBar = ({ stats, getColor }) => {
    const defaultGetColor = (color, shade) => {
        const colors = {
            warning: { 500: '#f59e0b' },
            primary: { 500: '#3b82f6' },
            success: { 500: '#22c55e' }
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
        </div>
    );
};

/**
 * Хелпер для маппинга статусов очереди
 */
export const getQueueStatusInfo = (status) => {
    const statusMap = {
        waiting: { label: 'Ожидает', variant: 'warning', color: '#f59e0b' },
        called: { label: 'Вызван', variant: 'primary', color: '#3b82f6' },
        calling: { label: 'Вызывается', variant: 'primary', color: '#3b82f6' },
        in_cabinet: { label: 'В кабинете', variant: 'info', color: '#06b6d4' },
        in_service: { label: 'На приёме', variant: 'info', color: '#06b6d4' },
        diagnostics: { label: 'На обследовании', variant: 'info', color: '#8b5cf6' },
        served: { label: 'Обслужен', variant: 'success', color: '#22c55e' },
        completed: { label: 'Завершён', variant: 'success', color: '#22c55e' },
        done: { label: 'Завершён', variant: 'success', color: '#22c55e' },
        incomplete: { label: 'Не завершён', variant: 'danger', color: '#ef4444' },
        no_show: { label: 'Не явился', variant: 'danger', color: '#ef4444' },
        cancelled: { label: 'Отменён', variant: 'secondary', color: '#6b7280' }
    };

    return statusMap[status] || { label: status, variant: 'default', color: '#6b7280' };
};

export default QueueActionButtons;
