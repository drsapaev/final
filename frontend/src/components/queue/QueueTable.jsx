import {
  Badge, Icon,
} from '../ui/macos';
import PropTypes from 'prop-types';
import { formatRegistrarTime } from '../../utils/dateUtils';
// UX Audit Registrar #3: все inline-стили перенесены в QueueTable.css.
import './QueueTable.css';

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
            <div className="qt-empty-state">
                <Icon name="person.crop.circle.badge.questionmark" size="large" className="qt-empty-state-icon" />
                <p>{t?.selectDoctor || 'Выберите специалиста'}</p>
            </div>
        );
    }

    // If loading
    if (loading) {
        return (
            <div className="qt-empty-state">
                <div className="mqm-spinner qt-loading-spinner"></div>
                <p>Загрузка очереди...</p>
            </div>
        );
    }

    // If no queue data
    if (!queueData) {
        return (
            <div className="qt-empty-state">
                <Icon name="exclamationmark.triangle" size="large" className="qt-empty-state-icon-warning" />
                <p>{t?.queueNotFound || 'Очередь не найдена'}</p>
                <p className="qt-empty-state-hint">
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
            <div className="qt-empty-state">
                <Icon name="person.2.slash" size="large" className="qt-empty-state-icon" />
                <p>{t?.queueEmpty || 'Очередь пуста'}</p>
                <p className="qt-empty-state-hint">
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
                <Icon name={config.icon} size="small" className="qt-status-badge-icon" />
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
        <div className="qt-table-container">
            <div className="admin-table-wrapper">
                <table className="qt-table">
                    <thead>
                        <tr className="qt-table-header-row">
                            <th className="qt-table-th">№</th>
                            <th className="qt-table-th">{t?.patient || 'Пациент'}</th>
                            <th className="qt-table-th">{t?.phone || 'Телефон'}</th>
                            <th className="qt-table-th">{t?.time || 'Время'}</th>
                            <th className="qt-table-th">{t?.status || 'Статус'}</th>
                            <th className="qt-table-th-right">{t?.actions || 'Действия'}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {entries.map((entry, index) => (
                            <tr
                                key={entry.id || index}
                                className={entry.status === 'called' ? 'qt-table-row-called' : 'qt-table-row'}
                            >
                                <td className="qt-table-cell-number">
                                    {entry.queue_number || entry.number || index + 1}
                                </td>
                                <td className="qt-table-cell-primary">
                                    {entry.patient_name || entry.name || '—'}
                                    {/* PR-23 P0 #3: source badge (QR vs Desk) */}
                                    {entry.source === 'online' || entry.source_kind === 'online_queue' || entry.source === 'qr' ? (
                                        <span style={{
                                            display: 'inline-block',
                                            marginLeft: '6px',
                                            padding: '1px 6px',
                                            borderRadius: '4px',
                                            fontSize: '10px',
                                            fontWeight: 600,
                                            background: 'rgba(139, 92, 246, 0.15)',
                                            color: '#7c3aed'
                                        }}>QR</span>
                                    ) : (
                                        <span style={{
                                            display: 'inline-block',
                                            marginLeft: '6px',
                                            padding: '1px 6px',
                                            borderRadius: '4px',
                                            fontSize: '10px',
                                            fontWeight: 500,
                                            background: 'rgba(100, 116, 139, 0.15)',
                                            color: '#64748b'
                                        }}>Desk</span>
                                    )}
                                </td>
                                <td className="qt-table-cell-phone">
                                    {entry.patient_phone || entry.phone || '—'}
                                </td>
                                <td className="qt-table-cell-secondary">
                                    {formatTime(entry.queue_time || entry.created_at || entry.timestamp)}
                                </td>
                                <td className="qt-table-cell-status">
                                    {getStatusBadge(entry.status)}
                                </td>
                                <td className="qt-table-cell-actions">
                                    {entry.status === 'called' && (
                                        <Badge variant="info">
                                            <Icon name="bell.fill" size="small" className="qt-status-badge-icon" />
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
