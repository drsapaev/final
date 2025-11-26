import React from 'react';
import { Badge, Button, Icon } from '../ui/macos';
import PropTypes from 'prop-types';

/**
 * QueueTable Component
 * Displays the current queue entries in a table format
 */
const QueueTable = ({
    queueData,
    effectiveDoctor,
    onGenerateQR,
    onCallPatient,
    loading,
    t
}) => {
    // If no queue data or no doctor selected
    if (!effectiveDoctor) {
        return (
            <div style={{
                padding: '48px 24px',
                textAlign: 'center',
                color: 'var(--mac-text-secondary)',
                fontSize: '14px'
            }}>
                <Icon name="person.crop.circle.badge.questionmark" size="large" style={{
                    marginBottom: '12px',
                    opacity: 0.5
                }} />
                <p>{t?.selectDoctor || 'Выберите специалиста'}</p>
            </div>
        );
    }

    // If loading
    if (loading) {
        return (
            <div style={{
                padding: '48px 24px',
                textAlign: 'center',
                color: 'var(--mac-text-secondary)',
                fontSize: '14px'
            }}>
                <div className="mqm-spinner" style={{ margin: '0 auto 12px' }}></div>
                <p>Загрузка очереди...</p>
            </div>
        );
    }

    // If no queue data
    if (!queueData) {
        return (
            <div style={{
                padding: '48px 24px',
                textAlign: 'center',
                color: 'var(--mac-text-secondary)',
                fontSize: '14px'
            }}>
                <Icon name="exclamationmark.triangle" size="large" style={{
                    marginBottom: '12px',
                    opacity: 0.5,
                    color: 'var(--mac-warning)'
                }} />
                <p>{t?.queueNotFound || 'Очередь не найдена'}</p>
                <p style={{ fontSize: '12px', marginTop: '8px' }}>
                    Попробуйте сгенерировать QR код для создания очереди
                </p>
            </div>
        );
    }

    // Get queue entries
    const entries = queueData?.entries || [];

    // If queue is empty
    if (entries.length === 0) {
        return (
            <div style={{
                padding: '48px 24px',
                textAlign: 'center',
                color: 'var(--mac-text-secondary)',
                fontSize: '14px'
            }}>
                <Icon name="person.2.slash" size="large" style={{
                    marginBottom: '12px',
                    opacity: 0.5
                }} />
                <p>{t?.queueEmpty || 'Очередь пуста'}</p>
                <p style={{ fontSize: '12px', marginTop: '8px' }}>
                    Пациенты могут записаться через QR код
                </p>
            </div>
        );
    }

    // Status badge variants
    const getStatusBadge = (status) => {
        const statusMap = {
            'waiting': { variant: 'warning', label: 'Ожидает', icon: 'clock' },
            'called': { variant: 'info', label: 'Вызван', icon: 'bell' },
            'in_progress': { variant: 'primary', label: 'На приеме', icon: 'person.fill' },
            'completed': { variant: 'success', label: 'Завершен', icon: 'checkmark.circle' },
            'cancelled': { variant: 'secondary', label: 'Отменен', icon: 'xmark.circle' },
            'no_show': { variant: 'secondary', label: 'Не явился', icon: 'person.crop.circle.badge.xmark' }
        };

        const config = statusMap[status] || statusMap['waiting'];

        return (
            <Badge variant={config.variant}>
                <Icon name={config.icon} size="small" style={{ marginRight: '4px' }} />
                {config.label}
            </Badge>
        );
    };

    // Format time
    const formatTime = (timestamp) => {
        if (!timestamp) return '—';
        try {
            return new Date(timestamp).toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return '—';
        }
    };

    return (
        <div className="queue-table-container" style={{
            overflowX: 'auto',
            marginTop: '16px'
        }}>
            <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '14px'
            }}>
                <thead>
                    <tr style={{
                        borderBottom: '1px solid var(--mac-border)',
                        backgroundColor: 'var(--mac-bg-tertiary)'
                    }}>
                        <th style={{
                            padding: '12px 16px',
                            textAlign: 'left',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)',
                            whiteSpace: 'nowrap'
                        }}>
                            №
                        </th>
                        <th style={{
                            padding: '12px 16px',
                            textAlign: 'left',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.patient || 'Пациент'}
                        </th>
                        <th style={{
                            padding: '12px 16px',
                            textAlign: 'left',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.phone || 'Телефон'}
                        </th>
                        <th style={{
                            padding: '12px 16px',
                            textAlign: 'left',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.time || 'Время'}
                        </th>
                        <th style={{
                            padding: '12px 16px',
                            textAlign: 'left',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.status || 'Статус'}
                        </th>
                        <th style={{
                            padding: '12px 16px',
                            textAlign: 'right',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.actions || 'Действия'}
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {entries.map((entry, index) => (
                        <tr
                            key={entry.id || index}
                            style={{
                                borderBottom: '1px solid var(--mac-border)',
                                transition: 'background-color 0.2s ease',
                                backgroundColor: entry.status === 'called'
                                    ? 'rgba(0, 122, 255, 0.05)'
                                    : 'transparent'
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = entry.status === 'called'
                                    ? 'rgba(0, 122, 255, 0.05)'
                                    : 'transparent';
                            }}
                        >
                            <td style={{
                                padding: '12px 16px',
                                color: 'var(--mac-text-primary)',
                                fontWeight: '600',
                                fontSize: '16px'
                            }}>
                                {entry.queue_number || entry.number || index + 1}
                            </td>
                            <td style={{
                                padding: '12px 16px',
                                color: 'var(--mac-text-primary)'
                            }}>
                                {entry.patient_name || entry.name || '—'}
                            </td>
                            <td style={{
                                padding: '12px 16px',
                                color: 'var(--mac-text-secondary)',
                                fontFamily: 'monospace'
                            }}>
                                {entry.patient_phone || entry.phone || '—'}
                            </td>
                            <td style={{
                                padding: '12px 16px',
                                color: 'var(--mac-text-secondary)'
                            }}>
                                {formatTime(entry.created_at || entry.timestamp)}
                            </td>
                            <td style={{
                                padding: '12px 16px'
                            }}>
                                {getStatusBadge(entry.status)}
                            </td>
                            <td style={{
                                padding: '12px 16px',
                                textAlign: 'right'
                            }}>
                                {entry.status === 'waiting' && (
                                    <Button
                                        size="sm"
                                        variant="primary"
                                        onClick={onCallPatient}
                                        disabled={loading}
                                    >
                                        <Icon name="bell.fill" size="small" style={{ marginRight: '4px' }} />
                                        {t?.call || 'Вызвать'}
                                    </Button>
                                )}
                                {entry.status === 'called' && (
                                    <Badge variant="info">
                                        <Icon name="bell.fill" size="small" style={{ marginRight: '4px' }} />
                                        {t?.called || 'Вызван'}
                                    </Badge>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

QueueTable.propTypes = {
    queueData: PropTypes.shape({
        entries: PropTypes.array,
        is_open: PropTypes.bool,
        online_start_time: PropTypes.string
    }),
    effectiveDoctor: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    onGenerateQR: PropTypes.func,
    onCallPatient: PropTypes.func,
    loading: PropTypes.bool,
    t: PropTypes.object
};

QueueTable.defaultProps = {
    queueData: null,
    effectiveDoctor: null,
    onGenerateQR: () => { },
    onCallPatient: () => { },
    loading: false,
    t: {}
};

export default QueueTable;
