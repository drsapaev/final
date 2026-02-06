/**
 * EMRStatusIndicator - Psychological anchor for the doctor
 * 
 * States:
 * - Saving... (animated)
 * - Unsaved (warning)
 * - Saved X min ago
 * - Conflict (critical)
 * - Error (with 401/403 distinction)
 * 
 * Rules:
 * - NEVER show "Saved" if isDirty = true
 * - Shows "Last autosave at..." with tooltip
 */

import React, { useState, useEffect } from 'react';
import './EMRStatusIndicator.css';

/**
 * Format relative time (e.g., "2 мин назад")
 */
function formatRelativeTime(date) {
    if (!date) return null;

    const now = Date.now();
    const then = typeof date === 'string' ? new Date(date).getTime() : date;
    const diffMs = now - then;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);

    if (diffSec < 10) return 'только что';
    if (diffSec < 60) return `${diffSec} сек назад`;
    if (diffMin < 60) return `${diffMin} мин назад`;
    if (diffHour < 24) return `${diffHour} ч назад`;

    return new Date(then).toLocaleDateString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
    });
}

/**
 * Format absolute time for tooltip
 */
function formatAbsoluteTime(date) {
    if (!date) return '';
    const d = typeof date === 'string' ? new Date(date) : new Date(date);
    return d.toLocaleString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

/**
 * EMRStatusIndicator Component
 * 
 * @param {Object} props
 * @param {string} props.status - Current status: idle | saving | conflict | error
 * @param {boolean} props.isDirty - Has unsaved changes
 * @param {boolean} props.isSigned - EMR is signed
 * @param {boolean} props.isAmended - EMR has amendments
 * @param {string|number} props.lastSaved - Last save timestamp
 * @param {string|number} props.lastAutosave - Last autosave timestamp
 * @param {Object} props.error - Error object or message
 * @param {Object} props.conflict - Conflict info
 * @param {number} props.version - Current version
 * @param {Object} props.autosaveConfig - Autosave configuration
 */
export function EMRStatusIndicator({
    status = 'idle',
    isDirty = false,
    isSigned = false,
    isAmended = false,
    lastSaved,
    lastAutosave,
    error,
    conflict,
    version,
    autosaveConfig = { debounceMs: 3000, enabled: true },
}) {
    // Update relative time every 10 seconds
    const [, setTick] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => setTick(t => t + 1), 10000);
        return () => clearInterval(interval);
    }, []);

    // =========================================================================
    // Determine what to show
    // =========================================================================

    let content;
    let className = 'emr-status-indicator';
    let tooltip = '';

    // Priority order: error > conflict > saving > signed > dirty > saved

    if (status === 'error' || error) {
        // Error state
        const errorMsg = typeof error === 'string' ? error : error?.message || 'Ошибка';
        const is401 = error?.status === 401 || errorMsg.includes('401');
        const is403 = error?.status === 403 || errorMsg.includes('403');

        if (is401) {
            content = '🔒 Сессия истекла';
            tooltip = 'Необходимо войти заново';
        } else if (is403) {
            content = '🚫 Нет доступа';
            tooltip = 'У вас нет прав на редактирование';
        } else {
            content = `❌ ${errorMsg}`;
            tooltip = 'Произошла ошибка при сохранении';
        }
        className += ' emr-status-indicator--error';
    }

    else if (status === 'conflict' || conflict) {
        content = '⚠️ Конфликт версий';
        tooltip = conflict
            ? `Ваша версия: ${conflict.yourVersion}, текущая: ${conflict.serverVersion}`
            : 'Кто-то изменил документ';
        className += ' emr-status-indicator--conflict';
    }

    else if (status === 'saving') {
        content = (
            <>
                <span className="emr-status-spinner">💾</span>
                Сохранение...
            </>
        );
        tooltip = 'Идёт сохранение';
        className += ' emr-status-indicator--saving';
    }

    else if (isSigned) {
        content = isAmended ? '📝 Подписана (с поправками)' : '✅ Подписана';
        tooltip = isSigned && lastSaved
            ? `Подписана ${formatAbsoluteTime(lastSaved)}`
            : 'Документ подписан и защищён от изменений';
        className += ' emr-status-indicator--signed';
    }

    else if (isDirty) {
        // CRITICAL: Never show "Saved" if isDirty = true
        content = '● Есть изменения';

        // Show when next autosave will happen
        if (autosaveConfig?.enabled) {
            tooltip = `Автосохранение через ${Math.round(autosaveConfig.debounceMs / 1000)} сек`;
        } else {
            tooltip = 'Не забудьте сохранить';
        }
        className += ' emr-status-indicator--dirty';
    }

    else if (lastSaved || lastAutosave) {
        // Show last save time
        const saveTime = lastSaved || lastAutosave;
        const relativeTime = formatRelativeTime(saveTime);
        const absoluteTime = formatAbsoluteTime(saveTime);

        content = `✓ ${relativeTime}`;
        tooltip = `Сохранено в ${absoluteTime}`;

        if (lastAutosave && autosaveConfig?.enabled) {
            tooltip += ` (автосохранение каждые ${Math.round(autosaveConfig.debounceMs / 1000)} сек)`;
        }
        className += ' emr-status-indicator--saved';
    }

    else {
        content = 'Новый документ';
        tooltip = 'Начните вводить данные';
        className += ' emr-status-indicator--new';
    }

    // =========================================================================
    // Render
    // =========================================================================

    return (
        <div className={className} title={tooltip}>
            <span className="emr-status-indicator__content">
                {content}
            </span>

            {version > 0 && (
                <span className="emr-status-indicator__version" title={`Версия ${version}`}>
                    v{version}
                </span>
            )}
        </div>
    );
}

export default EMRStatusIndicator;
