import {
  Badge, Icon,
} from '../ui/macos';
import PropTypes from 'prop-types';
import { formatRegistrarTime } from '../../utils/dateUtils';

/**
 * QueueTable Component
 * Displays the current queue entries in a table format
 */
const QueueTable = ({
    queueData = null,
    effectiveDoctor = null,
    loading = false,
    t = {}
}) => {
    // If no queue data or no doctor selected
    if (!effectiveDoctor) {
        return (
            <div style={{
                padding: '48px 24px',
                textAlign: 'center',
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-base)'
            }}>
                <Icon name="person.crop.circle.badge.questionmark" size="large" style={{
                    marginBottom: 'var(--mac-spacing-3)',
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
                fontSize: 'var(--mac-font-size-base)'
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
                fontSize: 'var(--mac-font-size-base)'
            }}>
                <Icon name="exclamationmark.triangle" size="large" style={{
                    marginBottom: 'var(--mac-spacing-3)',
                    opacity: 0.5,
                    color: 'var(--mac-warning)'
                }} />
                <p>{t?.queueNotFound || 'Очередь не найдена'}</p>
                <p style={{ fontSize: 'var(--mac-font-size-xs)', marginTop: 'var(--mac-spacing-2)' }}>
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
                fontSize: 'var(--mac-font-size-base)'
            }}>
                <Icon name="person.2.slash" size="large" style={{
                    marginBottom: 'var(--mac-spacing-3)',
                    opacity: 0.5
                }} />
                <p>{t?.queueEmpty || 'Очередь пуста'}</p>
                <p style={{ fontSize: 'var(--mac-font-size-xs)', marginTop: 'var(--mac-spacing-2)' }}>
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

        const config = statusMap[status] || {
            variant: 'secondary',
            label: status || '—',
            icon: 'questionmark.circle'
        };

        return (
            <Badge variant={config.variant}>
                <Icon name={config.icon} size="small" style={{ marginRight: 'var(--mac-spacing-1)' }} />
                {config.label}
            </Badge>
        );
    };

    // Format time
    const formatTime = (timestamp) => {
        if (!timestamp) return '—';
        try {
            return formatRegistrarTime(timestamp) || 'вЂ”';
        } catch {
            return '—';
        }
    };

    return (
        <div className="queue-table-container" style={{
            overflowX: 'auto',
            marginTop: 'var(--mac-spacing-4)'
        }}>
            <div className="admin-table-wrapper">
<table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 'var(--mac-font-size-base)'
            }}>
                <thead>
                    <tr style={{
                        borderBottom: '1px solid var(--mac-border)',
                        backgroundColor: 'var(--mac-bg-tertiary)'
                    }}>
                        <th style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                            textAlign: 'left',
                            fontWeight: 'var(--mac-font-weight-semibold)',
                            color: 'var(--mac-text-primary)',
                            whiteSpace: 'nowrap'
                        }}>
                            №
                        </th>
                        <th style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                            textAlign: 'left',
                            fontWeight: 'var(--mac-font-weight-semibold)',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.patient || 'Пациент'}
                        </th>
                        <th style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                            textAlign: 'left',
                            fontWeight: 'var(--mac-font-weight-semibold)',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.phone || 'Телефон'}
                        </th>
                        <th style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                            textAlign: 'left',
                            fontWeight: 'var(--mac-font-weight-semibold)',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.time || 'Время'}
                        </th>
                        <th style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                            textAlign: 'left',
                            fontWeight: 'var(--mac-font-weight-semibold)',
                            color: 'var(--mac-text-primary)'
                        }}>
                            {t?.status || 'Статус'}
                        </th>
                        <th style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                            textAlign: 'right',
                            fontWeight: 'var(--mac-font-weight-semibold)',
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
                                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                                color: 'var(--mac-text-primary)',
                                fontWeight: 'var(--mac-font-weight-semibold)',
                                fontSize: 'var(--mac-font-size-lg)'
                            }}>
                                {entry.queue_number || entry.number || index + 1}
                            </td>
                            <td style={{
                                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                                color: 'var(--mac-text-primary)'
                            }}>
                                {entry.patient_name || entry.name || '—'}
                            </td>
                            <td style={{
                                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                                color: 'var(--mac-text-secondary)',
                                fontFamily: 'monospace'
                            }}>
                                {entry.patient_phone || entry.phone || '—'}
                            </td>
                            <td style={{
                                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                                color: 'var(--mac-text-secondary)'
                            }}>
                                {formatTime(entry.created_at || entry.timestamp)}
                            </td>
                            <td style={{
                                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)'
                            }}>
                                {getStatusBadge(entry.status)}
                            </td>
                            <td style={{
                                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                                textAlign: 'right'
                            }}>
                                {entry.status === 'called' && (
                                    <Badge variant="info">
                                        <Icon name="bell.fill" size="small" style={{ marginRight: 'var(--mac-spacing-1)' }} />
                                        {t?.called || 'Вызван'}
                                    </Badge>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
</div>
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
    loading: PropTypes.bool,
    t: PropTypes.object
};

export default QueueTable;
