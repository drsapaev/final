/**
 * EMRDiffViewer - Field-level comparison of two EMR versions
 * 
 * Features:
 * - Compare vX ↔ vY
 * - Field-by-field diff: added / changed / removed
 * - JSON → human-readable labels
 * - Fixed field order
 * - Hides empty/unchanged fields
 * 
 * NOT included (by design):
 * - Raw JSON view
 * - Character-level diff
 * - Side-by-side editor
 */

import React, { useState, useEffect } from 'react';
import { apiClient } from '../../api/client';
import './EMRDiffViewer.css';

/**
 * Human-readable field labels (Russian)
 */
const FIELD_LABELS = {
    complaints: 'Жалобы',
    anamnesis: 'Анамнез',
    examination: 'Осмотр',
    diagnosis: 'Диагноз',
    icd10_code: 'Код МКБ-10',
    treatment: 'Лечение',
    recommendations: 'Рекомендации',
    notes: 'Примечания',
    vitals: 'Витальные показатели',
    lab_results: 'Лабораторные данные',
    prescriptions: 'Назначения',
};

/**
 * Fixed field order for consistent display
 */
const FIELD_ORDER = [
    'complaints',
    'anamnesis',
    'examination',
    'vitals',
    'lab_results',
    'diagnosis',
    'icd10_code',
    'treatment',
    'prescriptions',
    'recommendations',
    'notes',
];

/**
 * Get human-readable field label
 */
function getFieldLabel(field) {
    return FIELD_LABELS[field] || field;
}

/**
 * Format value for display
 */
function formatValue(value) {
    if (value === null || value === undefined) {
        return '—';
    }
    if (typeof value === 'object') {
        // Handle nested objects/arrays
        if (Array.isArray(value)) {
            return value.length > 0 ? value.map(v => formatValue(v)).join(', ') : '—';
        }
        // Object - format key-value pairs
        return Object.entries(value)
            .filter(([, v]) => v !== null && v !== undefined && v !== '')
            .map(([k, v]) => `${getFieldLabel(k)}: ${formatValue(v)}`)
            .join('; ') || '—';
    }
    if (typeof value === 'boolean') {
        return value ? 'Да' : 'Нет';
    }
    return String(value || '—');
}

/**
 * EMRDiffViewer Component
 * 
 * @param {Object} props
 * @param {number} props.visitId - Visit ID
 * @param {number} props.versionFrom - Left version for comparison
 * @param {number} props.versionTo - Right version for comparison
 * @param {Function} props.onClose - Close callback
 */
export function EMRDiffViewer({
    visitId,
    versionFrom,
    versionTo,
    onClose,
}) {
    const [diff, setDiff] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Load diff when versions change
    useEffect(() => {
        if (!visitId || !versionFrom || !versionTo) return;

        const loadDiff = async () => {
            setLoading(true);
            setError(null);

            try {
                const response = await apiClient.get(
                    `/v2/emr/${visitId}/diff?v1=${versionFrom}&v2=${versionTo}`
                );
                setDiff(response.data);
            } catch (err) {
                console.error('Failed to load diff:', err);
                setError(err.message || 'Не удалось загрузить сравнение');
            } finally {
                setLoading(false);
            }
        };

        loadDiff();
    }, [visitId, versionFrom, versionTo]);

    /**
     * Sort changes by fixed field order
     */
    const sortedChanges = React.useMemo(() => {
        if (!diff?.changes) return [];

        return [...diff.changes].sort((a, b) => {
            const indexA = FIELD_ORDER.indexOf(a.field);
            const indexB = FIELD_ORDER.indexOf(b.field);

            // Fields not in order go to the end
            const orderA = indexA === -1 ? 999 : indexA;
            const orderB = indexB === -1 ? 999 : indexB;

            return orderA - orderB;
        });
    }, [diff?.changes]);

    /**
     * Get change type style
     */
    const getChangeTypeClass = (changeType) => {
        switch (changeType) {
            case 'added': return 'emr-diff__change--added';
            case 'removed': return 'emr-diff__change--removed';
            case 'modified': return 'emr-diff__change--modified';
            default: return '';
        }
    };

    /**
     * Get change type label
     */
    const getChangeTypeLabel = (changeType) => {
        switch (changeType) {
            case 'added': return '➕ Добавлено';
            case 'removed': return '➖ Удалено';
            case 'modified': return '✏️ Изменено';
            default: return changeType;
        }
    };

    // =========================================================================
    // RENDER
    // =========================================================================

    return (
        <div className="emr-diff">
            {/* Header */}
            <div className="emr-diff__header">
                <h3>
                    📊 Сравнение: v{versionFrom} → v{versionTo}
                </h3>
                {onClose && (
                    <button className="emr-diff__close" onClick={onClose}>
                        ×
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="emr-diff__content">
                {loading && (
                    <div className="emr-diff__loading">
                        Загрузка...
                    </div>
                )}

                {error && (
                    <div className="emr-diff__error">
                        ❌ {error}
                    </div>
                )}

                {!loading && !error && diff && (
                    <>
                        {/* Summary */}
                        <div className="emr-diff__summary">
                            {diff.summary || `${sortedChanges.length} изменений`}
                        </div>

                        {/* No changes */}
                        {sortedChanges.length === 0 && (
                            <div className="emr-diff__no-changes">
                                ✓ Нет различий между версиями
                            </div>
                        )}

                        {/* Changes list */}
                        {sortedChanges.length > 0 && (
                            <ul className="emr-diff__list">
                                {sortedChanges.map((change, index) => (
                                    <li
                                        key={`${change.field}-${index}`}
                                        className={`emr-diff__change ${getChangeTypeClass(change.change_type)}`}
                                    >
                                        {/* Field header */}
                                        <div className="emr-diff__change-header">
                                            <span className="emr-diff__field">
                                                {getFieldLabel(change.field)}
                                            </span>
                                            <span className="emr-diff__change-type">
                                                {getChangeTypeLabel(change.change_type)}
                                            </span>
                                        </div>

                                        {/* Values */}
                                        <div className="emr-diff__values">
                                            {/* Old value (for modified/removed) */}
                                            {(change.change_type === 'modified' || change.change_type === 'removed') && (
                                                <div className="emr-diff__value emr-diff__value--old">
                                                    <span className="emr-diff__value-label">Было:</span>
                                                    <span className="emr-diff__value-content">
                                                        {formatValue(change.old_value)}
                                                    </span>
                                                </div>
                                            )}

                                            {/* New value (for modified/added) */}
                                            {(change.change_type === 'modified' || change.change_type === 'added') && (
                                                <div className="emr-diff__value emr-diff__value--new">
                                                    <span className="emr-diff__value-label">Стало:</span>
                                                    <span className="emr-diff__value-content">
                                                        {formatValue(change.new_value)}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

export default EMRDiffViewer;
