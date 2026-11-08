
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

import { useState, useEffect, useRef } from 'react';
import type { ReactNode, ReactElement } from 'react';
import React from 'react';
import { FileText, Pencil, CheckCircle2, FilePenLine, RefreshCw, GitBranch } from 'lucide-react';
import { apiClient } from '../../api/client';
import logger from '../../utils/logger';
import './EMRHistoryPanel.css';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * Format date for display
 */
function formatDate(dateStr: string | number | null | undefined): string {
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

type ChangeType = 'created' | 'updated' | 'signed' | 'amended' | 'restored' | 'migrated' | string;

type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

interface HistoryRevision {
    id?: string | number;
    version?: string | number;
    change_type?: ChangeType;
    change_summary?: string;
    reason?: string;
    // EMRHIST-FE-001 (audit 3886, round 19): the backend history contract
    // (EMRRevisionSummary in backend/app/schemas/emr_v2.py) publishes
    // created_at/created_by. The legacy edited_at/edited_by keys are kept
    // only as a read fallback for older payloads.
    created_at?: string | number;
    created_by?: number;
    edited_at?: string | number;
    edited_by?: number;
}

export interface EMRHistoryPanelProps {
    visitId?: string | number;
    currentVersion?: string | number;
    selectedVersion?: string | number;
    onSelectVersion?: (version: string | number | undefined) => void;
    isOpen?: boolean;
    onClose?: () => void;
}

/**
 * Get action label in Russian
 */
function getActionLabel(changeType: ChangeType | undefined, t: TranslateFn): string {
    if (!changeType) return '';
    const labels: Record<string, string> = {
        created: t('misc.ehp_action_created'),
        updated: t('misc.ehp_action_updated'),
        signed: t('misc.ehp_action_signed'),
        amended: t('misc.ehp_action_amended'),
        restored: t('misc.ehp_action_restored'),
        migrated: t('misc.ehp_action_migrated'),
    };
    return labels[changeType] || changeType;
}

/**
 * Get action icon
 */
// UX Audit Doctor M-22: emoji → lucide-react icons.
function getActionIcon(changeType: ChangeType | undefined): ReactNode {
    const icons: Record<string, typeof FileText> = {
        created: FileText,
        updated: Pencil,
        signed: CheckCircle2,
        amended: FilePenLine,
        restored: RefreshCw,
        migrated: GitBranch,
    };
    const Icon = changeType ? icons[changeType] : undefined;
    return Icon ? <Icon size={14} /> : null;
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
}: EMRHistoryPanelProps): React.ReactElement | null {
    const { t: rawT } = useTranslation(); const t = rawT as TranslateFn;
    const [history, setHistory] = useState<HistoryRevision[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // EMRHIST-FE-002 (audit 3886, round 19): fetch results are bound to the
    // visit they were requested for. Every request takes an epoch; a
    // context switch (visitId/isOpen change) immediately clears the previous
    // snapshot and bumps the epoch, so a late response — or a late FAILURE —
    // of visit A can never render A's audit trail (or hide B's) while the
    // panel shows visit B.
    const fetchEpochRef = useRef(0);

    // Load history on mount or visitId change
    useEffect(() => {
        if (!isOpen) return;
        if (!visitId) {
            // Cleared context — nothing to show, no stale rows may survive.
            setHistory([]);
            setError(null);
            setLoading(false);
            return;
        }

        const epoch = fetchEpochRef.current + 1;
        fetchEpochRef.current = epoch;
        // Immediately drop the previous visit's rows while the new request
        // is in flight (they must not stay visible under the new context).
        setHistory([]);
        setError(null);
        setLoading(true);

        const loadHistory = async () => {
            try {
                const response = await apiClient.get(`/v2/emr/${visitId}/history`);
                if (epoch !== fetchEpochRef.current) return;
                setHistory(response.data.revisions || []);
            } catch (err) {
                if (epoch !== fetchEpochRef.current) return;
                logger.error('Failed to load history:', err);
                setError((err instanceof Error ? err.message : String(err)) || t('misc.ehp_ne_udalos_zagruzit_istoriyu'));
            } finally {
                if (epoch === fetchEpochRef.current) setLoading(false);
            }
        };

        void loadHistory();
        return () => {
            fetchEpochRef.current += 1;
        };
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
                        title={t('misc.ehp_zakryt')}
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
                        {history.map((revision: HistoryRevision) => {
                            const isCurrentVersion = revision.version === currentVersion;
                            const isSelected = revision.version === selectedVersion;

                            return (
                                <li
                                    key={revision.id}
                                    className={`emr-history-panel__item ${isCurrentVersion ? 'emr-history-panel__item--current' : ''} ${isSelected ? 'emr-history-panel__item--selected' : ''}`}
                                    onClick={() => onSelectVersion?.(revision.version)}
                                    onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => {
                                        if (event.key === 'Enter' || event.key === ' ') {
                                            event.preventDefault();
                                            onSelectVersion?.(revision.version);
                                        }
                                    }}
                                    role="button"
                                    tabIndex={0}
                                    title={t('misc.ehp_vybrat_versiyu_revision_vers', { version: revision.version })}
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
                                            {getActionLabel(revision.change_type, t)}
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

                                    {/* Footer: date and author — EMRHIST-FE-001 (audit
                                        3886, round 19): canonical DTO keys
                                        created_at/created_by (with the legacy
                                        edited_at/edited_by as read-only
                                        fallback); no invented names. */}
                                    <div className="emr-history-panel__footer">
                                        <span className="emr-history-panel__date">
                                            {formatDate(revision.created_at ?? revision.edited_at)}
                                        </span>
                                        {(() => {
                                            const author = revision.created_by ?? revision.edited_by;
                                            return author != null && author > 0 ? (
                                                <span className="emr-history-panel__author">
                                                    👤 #{author}
                                                </span>
                                            ) : null;
                                        })()}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            {/* Footer: hint */}
            <div className="emr-history-panel__hint">
                Нажмите на версию для сравнения
            </div>
        </div>
    );
}

export default EMRHistoryPanel;

