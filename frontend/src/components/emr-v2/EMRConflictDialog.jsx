/**
 * EMRConflictDialog - Conflict resolution UI (for 409 errors)
 * 
 * When conflict detected, user MUST choose:
 * - 🔄 Reload from server (discard local changes)
 * - 🧾 Compare changes (see diff before deciding)
 * - 📝 Create amendment (if EMR is signed)
 * 
 * Forbidden (by design):
 * - Auto-merge
 * - Silent overwrite
 * - "We did it for you"
 * 
 * UX Principle:
 * Nothing happens without a conscious click by the doctor
 */

import React, { useState } from 'react';
import './EMRConflictDialog.css';

/**
 * EMRConflictDialog Component
 * 
 * @param {Object} props
 * @param {Object} props.conflict - Conflict info from server
 * @param {number} props.conflict.serverVersion - Current server version
 * @param {number} props.conflict.yourVersion - User's version
 * @param {number} props.conflict.lastEditedBy - Who last edited
 * @param {string} props.conflict.lastEditedAt - When last edited
 * @param {boolean} props.isSigned - Is EMR already signed
 * @param {Function} props.onReload - Reload from server callback
 * @param {Function} props.onCompare - Show diff callback
 * @param {Function} props.onAmend - Create amendment callback (signed only)
 * @param {Function} props.onForceOverwrite - Force overwrite callback (not recommended)
 * @param {boolean} props.loading - Is action in progress
 */
export function EMRConflictDialog({
    conflict,
    isSigned = false,
    onReload,
    onCompare,
    onAmend,
    onForceOverwrite,
    loading = false,
}) {
    const [showAdvanced, setShowAdvanced] = useState(false);

    if (!conflict) return null;

    const formatTime = (dateStr) => {
        if (!dateStr) return '—';
        return new Date(dateStr).toLocaleString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit',
            day: '2-digit',
            month: '2-digit',
        });
    };

    return (
        <div className="emr-conflict-overlay">
            <div className="emr-conflict-dialog">
                {/* Header */}
                <div className="emr-conflict-dialog__header">
                    <span className="emr-conflict-dialog__icon">⚠️</span>
                    <h2>Конфликт версий</h2>
                </div>

                {/* Description */}
                <div className="emr-conflict-dialog__body">
                    <p className="emr-conflict-dialog__lead">
                        Документ был изменён другим пользователем, пока вы работали.
                    </p>

                    {/* Version info */}
                    <div className="emr-conflict-dialog__info">
                        <div className="emr-conflict-dialog__info-row">
                            <span className="emr-conflict-dialog__info-label">Ваша версия:</span>
                            <span className="emr-conflict-dialog__info-value">
                                v{conflict.yourVersion}
                            </span>
                        </div>
                        <div className="emr-conflict-dialog__info-row">
                            <span className="emr-conflict-dialog__info-label">Версия на сервере:</span>
                            <span className="emr-conflict-dialog__info-value emr-conflict-dialog__info-value--new">
                                v{conflict.serverVersion}
                            </span>
                        </div>
                        {conflict.lastEditedAt && (
                            <div className="emr-conflict-dialog__info-row">
                                <span className="emr-conflict-dialog__info-label">Изменено:</span>
                                <span className="emr-conflict-dialog__info-value">
                                    {formatTime(conflict.lastEditedAt)}
                                </span>
                            </div>
                        )}
                        {conflict.lastEditedBy > 0 && (
                            <div className="emr-conflict-dialog__info-row">
                                <span className="emr-conflict-dialog__info-label">Кем:</span>
                                <span className="emr-conflict-dialog__info-value">
                                    Пользователь #{conflict.lastEditedBy}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Warning */}
                    <div className="emr-conflict-dialog__warning">
                        ⚡ Ваши несохранённые изменения могут быть потеряны.
                    </div>
                </div>

                {/* Primary Actions */}
                <div className="emr-conflict-dialog__actions">
                    {/* Compare - always recommended first */}
                    <button
                        className="emr-conflict-btn emr-conflict-btn--primary"
                        onClick={onCompare}
                        disabled={loading}
                    >
                        🧾 Сравнить изменения
                    </button>

                    {/* Reload from server */}
                    <button
                        className="emr-conflict-btn emr-conflict-btn--secondary"
                        onClick={onReload}
                        disabled={loading}
                    >
                        🔄 Загрузить новую версию
                        <span className="emr-conflict-btn__hint">
                            (мои изменения будут потеряны)
                        </span>
                    </button>

                    {/* Amendment option (only for signed EMRs) */}
                    {isSigned && onAmend && (
                        <button
                            className="emr-conflict-btn emr-conflict-btn--warning"
                            onClick={onAmend}
                            disabled={loading}
                        >
                            📝 Создать поправку
                            <span className="emr-conflict-btn__hint">
                                (сохранить как amendment)
                            </span>
                        </button>
                    )}
                </div>

                {/* Advanced options (hidden by default) */}
                <div className="emr-conflict-dialog__advanced">
                    {!showAdvanced ? (
                        <button
                            className="emr-conflict-dialog__advanced-toggle"
                            onClick={() => setShowAdvanced(true)}
                        >
                            Расширенные опции...
                        </button>
                    ) : (
                        <div className="emr-conflict-dialog__advanced-content">
                            <p className="emr-conflict-dialog__advanced-warning">
                                ⚠️ Используйте с осторожностью. Это может привести к потере данных других пользователей.
                            </p>
                            <button
                                className="emr-conflict-btn emr-conflict-btn--danger"
                                onClick={onForceOverwrite}
                                disabled={loading}
                            >
                                💪 Перезаписать принудительно
                                <span className="emr-conflict-btn__hint">
                                    (данные сервера будут заменены)
                                </span>
                            </button>
                        </div>
                    )}
                </div>

                {/* Loading indicator */}
                {loading && (
                    <div className="emr-conflict-dialog__loading">
                        Обработка...
                    </div>
                )}
            </div>
        </div>
    );
}

export default EMRConflictDialog;
