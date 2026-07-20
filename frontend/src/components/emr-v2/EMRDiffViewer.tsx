
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
import PropTypes from 'prop-types';
import { apiClient } from '../../api/client';
import logger from '../../utils/logger';
import './EMRDiffViewer.css';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * Human-readable field labels (Russian)
 */
const getFieldLabels = (t) => ({
    complaints: t('misc.edv_field_complaints'),
    anamnesis: t('misc.edv_field_anamnesis'),
    examination: t('misc.edv_field_examination'),
    diagnosis: t('misc.edv_field_diagnosis'),
    icd10_code: t('misc.edv_field_icd10_code'),
    treatment: t('misc.edv_field_treatment'),
    recommendations: t('misc.edv_field_recommendations'),
    notes: t('misc.edv_field_notes'),
    vitals: t('misc.edv_field_vitals'),
    lab_results: t('misc.edv_field_lab_results'),
    prescriptions: t('misc.edv_field_prescriptions'),
});

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
function getFieldLabel(field, t) {
    return getFieldLabels(t)[field] || field;
}

/**
 * Format value for display
 */
function formatValue(value, t) {
    if (value === null || value === undefined) {
        return '—';
    }
    if (typeof value === 'object') {
        // Handle nested objects/arrays
        if (Array.isArray(value)) {
            return value.length > 0 ? value.map(v => formatValue(v, t)).join(', ') : '—';
        }
        // Object - format key-value pairs
        return Object.entries(value)
            .filter(([, v]) => v !== null && v !== undefined && v !== '')
            .map(([k, v]) => `${getFieldLabel(k, t)}: ${formatValue(v, t)}`)
            .join('; ') || '—';
    }
    if (typeof value === 'boolean') {
        return value ? t('misc.edv_yes') : t('misc.edv_no');
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
    const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
                logger.error('Failed to load diff:', err);
                setError(err.message || t('misc.edv_ne_udalos_zagruzit_sravnenie'));
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
            case 'added': return t('misc.edv_dobavleno');
            case 'removed': return t('misc.edv_udaleno');
            case 'modified': return t('misc.edv_izmeneno');
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
                            {diff.summary || t('misc.edv_sortedchanges_length_izmenen', { length: sortedChanges.length })}
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
                                                {getFieldLabel(change.field, t)}
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
                                                    <span className="emr-diff__value-label">{t('misc.edv_bylo')}</span>
                                                    <span className="emr-diff__value-content">
                                                        {formatValue(change.old_value, t)}
                                                    </span>
                                                </div>
                                            )}

                                            {/* New value (for modified/added) */}
                                            {(change.change_type === 'modified' || change.change_type === 'added') && (
                                                <div className="emr-diff__value emr-diff__value--new">
                                                    <span className="emr-diff__value-label">{t('misc.edv_stalo')}</span>
                                                    <span className="emr-diff__value-content">
                                                        {formatValue(change.new_value, t)}
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

EMRDiffViewer.propTypes = {
    visitId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    versionFrom: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    versionTo: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    onClose: PropTypes.func,
};
