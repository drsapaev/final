// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

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

import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';
import './EMRStatusIndicator.css';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * Format relative time (e.g., "2 мин назад")
 */
function formatRelativeTime(date, t) {
    if (!date) return null;

    const now = Date.now();
    const then = typeof date === 'string' ? new Date(date).getTime() : date;
    const diffMs = now - then;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);

    if (diffSec < 10) return t('misc.esi_tolko_chto');
    if (diffSec < 60) return t('misc.esi_sek_nazad', { count: diffSec });
    if (diffMin < 60) return t('misc.esi_min_nazad', { count: diffMin });
    if (diffHour < 24) return t('misc.esi_ch_nazad', { count: diffHour });

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
    const { t } = useTranslation();
    // Update relative time every 10 seconds
    const [, setTick] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => setTick(prev => prev + 1), 10000);
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
        const errorMsg = typeof error === 'string' ? error : error?.message || t('misc.esi_oshibka');
        const is401 = error?.status === 401 || errorMsg.includes('401');
        const is403 = error?.status === 403 || errorMsg.includes('403');

        if (is401) {
            content = t('misc.esi_sessiya_istekla');
            tooltip = t('misc.esi_neobhodimo_voyti_zanovo');
        } else if (is403) {
            content = t('misc.esi_net_dostupa');
            tooltip = t('misc.esi_u_vas_net_prav_na_redaktirov');
        } else {
            content = `❌ ${errorMsg}`;
            tooltip = t('misc.esi_proizoshla_oshibka_pri_sohra');
        }
        className += ' emr-status-indicator--error';
    }

    else if (status === 'conflict' || conflict) {
        content = t('misc.esi_konflikt_versiy');
        tooltip = conflict
            ? t('misc.esi_vasha_versiya_conflict_yourv', { yourVersion: conflict.yourVersion, serverVersion: conflict.serverVersion })
            : t('misc.esi_kto_to_izmenil_dokument');
        className += ' emr-status-indicator--conflict';
    }

    else if (status === 'saving') {
        content = (
            <>
                <span className="emr-status-spinner">💾</span>
                Сохранение...
            </>
        );
        tooltip = t('misc.esi_idyot_sohranenie');
        className += ' emr-status-indicator--saving';
    }

    else if (isSigned) {
        content = isAmended ? t('misc.esi_podpisana_s_popravkami') : t('misc.esi_podpisana');
        tooltip = isSigned && lastSaved
            ? t('misc.esi_podpisana_formatabsolutetime', { lastSaved: formatAbsoluteTime(lastSaved) })
            : t('misc.esi_dokument_podpisan_i_zaschisc');
        className += ' emr-status-indicator--signed';
    }

    else if (isDirty) {
        // CRITICAL: Never show "Saved" if isDirty = true
        content = t('misc.esi_est_izmeneniya');

        // Show when next autosave will happen
        if (autosaveConfig?.enabled) {
            tooltip = t('misc.esi_avtosohranenie_cherez_math_r', { debounceMs: Math.round(autosaveConfig.debounceMs / 1000) });
        } else {
            tooltip = t('misc.esi_ne_zabudte_sohranit');
        }
        className += ' emr-status-indicator--dirty';
    }

    else if (lastSaved || lastAutosave) {
        // Show last save time
        const saveTime = lastSaved || lastAutosave;
        const relativeTime = formatRelativeTime(saveTime, t);
        const absoluteTime = formatAbsoluteTime(saveTime);

        content = `✓ ${relativeTime}`;
        tooltip = t('misc.esi_sohraneno_v_absolutetime', { absoluteTime: absoluteTime });

        if (lastAutosave && autosaveConfig?.enabled) {
            tooltip += t('misc.esi_avtosohranenie_kazhdye_math_', { debounceMs: Math.round(autosaveConfig.debounceMs / 1000) });
        }
        className += ' emr-status-indicator--saved';
    }

    else {
        content = t('misc.esi_novyy_dokument');
        tooltip = t('misc.esi_nachnite_vvodit_dannye');
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
                <span className="emr-status-indicator__version" title={t('misc.esi_versiya_version', { version: version })}>
                    v{version}
                </span>
            )}
        </div>
    );
}

EMRStatusIndicator.propTypes = {
    status: PropTypes.oneOf(['idle', 'saving', 'conflict', 'error']),
    isDirty: PropTypes.bool,
    isSigned: PropTypes.bool,
    isAmended: PropTypes.bool,
    lastSaved: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.instanceOf(Date)]),
    lastAutosave: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.instanceOf(Date)]),
    error: PropTypes.oneOfType([
        PropTypes.string,
        PropTypes.shape({
            message: PropTypes.string,
            status: PropTypes.number,
        }),
    ]),
    conflict: PropTypes.shape({
        yourVersion: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        serverVersion: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    }),
    version: PropTypes.number,
    autosaveConfig: PropTypes.shape({
        debounceMs: PropTypes.number,
        enabled: PropTypes.bool,
    }),
};

export default EMRStatusIndicator;
