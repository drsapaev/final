/**
 * DataSourceIndicator — inline indicator showing data loading state.
 *
 * UX Audit Registrar #14: extracted from RegistrarPanel.jsx (lines 1283-1328).
 * Pure presentational component, no state — receives dataSource, count,
 * paginationInfo, and loadAppointments as props.
 */

import { memo } from 'react';
;
import { useTranslation } from '../../i18n/useTranslation';
import { AlertTriangle, ArrowUpDown, CheckCircle2, RefreshCw } from 'lucide-react';

interface DataSourceIndicatorProps {
  dataSource?: 'loading' | 'api' | 'error' | string;
  count?: number;
  paginationInfo?: { total?: number; hasMore?: boolean } | null;
  onRetry?: (opts?: Record<string, unknown>) => void;
  /** RQ-22 (F-18): true when displayed rows are kept after a failed
   *  refresh — the success look is replaced by an explicit staleness
   *  warning so the indicator never lies about freshness. */
  stale?: boolean;
}

const DataSourceIndicator = memo(({ dataSource, count, paginationInfo, onRetry, stale }: DataSourceIndicatorProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  // QW-03 fix: 'demo' state replaced with 'error' state — no more fake data.
  // DS-3: inline styles replaced with .registrar-ds-* CSS classes
  // i18n-unification: hardcoded Russian strings migrated to registrarPanel.* namespace
  if (dataSource === 'error') {
    return (
      <div className="registrar-ds-indicator registrar-ds-error">
        <AlertTriangle size={16} className="registrar-text-white" aria-hidden="true" />
        <span>{t('registrarPanel.ds_error_message')}</span>
        <button
          onClick={() => onRetry?.({ source: 'error_refresh_button', force: true })}
          className="registrar-ds-retry-btn">
          {t('registrarPanel.ds_retry')}
        </button>
      </div>
    );
  }

  if (dataSource === 'api') {
    // RQ-22 (F-18): rows kept after a failed refresh must not look fresh —
    // swap the success color for the explicit staleness warning + retry.
    if (stale) {
      return (
        <div className="registrar-ds-indicator registrar-ds-stale" role="status" aria-live="polite">
          <AlertTriangle size={16} className="registrar-text-white" aria-hidden="true" />
          <span>{t('registrarPanel.rp_worklist_stale_warning')}</span>
          <button
            onClick={() => onRetry?.({ source: 'stale_refresh_button', force: true })}
            className="registrar-ds-retry-btn">
            {t('registrarPanel.ds_retry')}
          </button>
        </div>
      );
    }
    return (
      <div className="registrar-ds-indicator registrar-ds-success">
        <CheckCircle2 size={16} className="registrar-text-white" aria-hidden="true" />
        <span>{t('registrarPanel.data_source_api')}</span>
        <span className="registrar-ds-count">
          {count} / {paginationInfo?.total ?? count}
        </span>
        {/* RQ-27.b (S-28): understandable manual refresh for the whole
            session — reuses the same onRetry plumbing the error/stale
            states already use; icon-only control, so the accessible name
            is pinned via aria-label (AXE-MOB-1 pattern). */}
        <button
          type="button"
          className="registrar-ds-retry-btn"
          aria-label={t('registrarPanel.ds_refresh')}
          title={t('registrarPanel.ds_refresh')}
          onClick={() => {
            // RQ-27.b (S-28): ONE understandable control refreshes the whole
            // session — the worklist reload rides the existing onRetry
            // plumbing, while the reference-data and queue-profile-tab
            // owners (useRegistrarData, Tabs) each run their throttled
            // silent revalidation on this same-context event. No polling,
            // no window-event knowledge required from the registrar.
            window.dispatchEvent(new CustomEvent('registrar:session-refresh'));
            onRetry?.({ source: 'manual_refresh_button', force: true });
          }}>
          <RefreshCw size={14} aria-hidden="true" />
        </button>
      </div>
    );
  }

  if (dataSource === 'loading') {
    return (
      <div className="registrar-ds-indicator registrar-ds-loading">
        <ArrowUpDown size={16} className="registrar-text-white" aria-hidden="true" />
        <span>{t('registrarPanel.loading')}</span>
      </div>
    );
  }

  return null;
});

DataSourceIndicator.displayName = 'DataSourceIndicator';

export default DataSourceIndicator;
