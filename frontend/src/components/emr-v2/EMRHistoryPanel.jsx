/**
 * EMRHistoryPanel - Read-only version history sidebar
 * 
 * Features:
 * - List of versions (version, date, doctor, action)
 * - Status badges: draft / signed / amended
 * - Click to select version (for diff comparison)
 * 
 * NOT included (by design):
 * - Inline diff
 * - Editing
 * - Restore from here
 */

import { useState, useEffect } from 'react';
import { apiClient } from '../../api/client';
import logger from '../../utils/logger';
import './EMRHistoryPanel.css';

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

/**
 * Get action label in Russian
 */
function getActionLabel(changeType) {
    const labels = {
        created: 'Создан',
        updated: 'Изменён',
        signed: 'Подписан',
        amended: 'Поправка',
        restored: 'Восстановлен',
        migrated: 'Миграция',
    };
    return labels[changeType] || changeType;
}

/**
 * Get action icon
 */
function getActionIcon(changeType) {
    const icons = {
        created: '📄',
        updated: '✏️',
        signed: '✅',
        amended: '📝',
        restored: '🔄',
        migrated: '🔀',
    };
    return icons[changeType] || '•';
}

/**
 * EMRHistoryPanel Component
 * 
 * @param {Object} props
 * @param {number} props.visitId - Visit ID to load history for
 * @param {number} props.currentVersion - Currently displayed version
 * @param {number} props.selectedVersion - Selected version for comparison
 * @param {Function} props.onSelectVersion - Callback when version is selected
 * @param {boolean} props.isOpen - Whether panel is open
 * @param {Function} props.onClose - Close callback
 */
export function EMRHistoryPanel({
    visitId,
    currentVersion,
    selectedVersion,
    onSelectVersion,
    isOpen = true,
    onClose,
}) {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Load history on mount or visitId change
    useEffect(() => {
        if (!visitId || !isOpen) return;

        const loadHistory = async () => {
            setLoading(true);
            setError(null);

            try {
                const response = await apiClient.get(`/v2/emr/${visitId}/history`);
                setHistory(response.data.revisions || []);
            } catch (err) {
                logger.error('Failed to load history:', err);
                setError(err.message || 'Не удалось загрузить историю');
            } finally {
                setLoading(false);
            }
        };

        loadHistory();
    }, [visitId, isOpen]);

    if (!isOpen) return null;

    return (
        <div className="emr-history-panel">
            {/* Header */}
            <div className="emr-history-panel__header">
                <h3>📜 История изменений</h3>
                {onClose && (
                    <button
                        className="emr-history-panel__close"
                        onClick={onClose}
                        title="Закрыть"
                    >
                        ×
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="emr-history-panel__content">
                {loading && (
                    <div className="emr-history-panel__loading">
                        Загрузка...
                    </div>
                )}

                {error && (
                    <div className="emr-history-panel__error">
                        ❌ {error}
                    </div>
                )}

                {!loading && !error && history.length === 0 && (
                    <div className="emr-history-panel__empty">
                        Нет истории изменений
                    </div>
                )}

                {!loading && !error && history.length > 0 && (
                    <ul className="emr-history-panel__list">
                        {history.map((revision) => {
                            const isCurrentVersion = revision.version === currentVersion;
                            const isSelected = revision.version === selectedVersion;

                            return (
                                <li
                                    key={revision.id}
                                    className={`emr-history-panel__item ${isCurrentVersion ? 'emr-history-panel__item--current' : ''} ${isSelected ? 'emr-history-panel__item--selected' : ''}`}
                                    onClick={() => onSelectVersion?.(revision.version)}
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter' || event.key === ' ') {
                                            event.preventDefault();
                                            onSelectVersion?.(revision.version);
                                        }
                                    }}
                                    role="button"
                                    tabIndex={0}
                                    title={`Выбрать версию ${revision.version} для сравнения`}
                                >
                                    {/* Version badge */}
                                    <div className="emr-history-panel__version">
                                        <span className="emr-history-panel__version-number">
                                            v{revision.version}
                                        </span>
                                        {isCurrentVersion && (
                                            <span className="emr-history-panel__current-badge">
                                                текущая
                                            </span>
                                        )}
                                    </div>

                                    {/* Action and summary */}
                                    <div className="emr-history-panel__action">
                                        <span className="emr-history-panel__action-icon">
                                            {getActionIcon(revision.change_type)}
                                        </span>
                                        <span className="emr-history-panel__action-label">
                                            {getActionLabel(revision.change_type)}
                                        </span>
                                    </div>

                                    {/* Summary (if available) */}
                                    {revision.change_summary && (
                                        <div className="emr-history-panel__summary">
                                            {revision.change_summary}
                                        </div>
                                    )}

                                    {/* Reason (for amendments) */}
                                    {revision.reason && (
                                        <div className="emr-history-panel__reason">
                                            💬 {revision.reason}
                                        </div>
                                    )}

                                    {/* Footer: date and author */}
                                    <div className="emr-history-panel__footer">
                                        <span className="emr-history-panel__date">
                                            {formatDate(revision.edited_at)}
                                        </span>
                                        {revision.edited_by > 0 && (
                                            <span className="emr-history-panel__author">
                                                👤 #{revision.edited_by}
                                            </span>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            {/* Footer: hint */}
            <div className="emr-history-panel__hint">
                💡 Нажмите на версию для сравнения
            </div>
        </div>
    );
}

export default EMRHistoryPanel;
