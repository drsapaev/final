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
import { AlertTriangle, ArrowUpDown, CheckCircle2 } from 'lucide-react';

interface DataSourceIndicatorProps {
  dataSource?: 'loading' | 'api' | 'error' | string;
  count?: number;
  paginationInfo?: { total?: number; hasMore?: boolean } | null;
  onRetry?: (opts?: Record<string, unknown>) => void;
}

const DataSourceIndicator = memo(({ dataSource, count, paginationInfo, onRetry }: DataSourceIndicatorProps) => {
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
    return (
      <div className="registrar-ds-indicator registrar-ds-success">
        <CheckCircle2 size={16} className="registrar-text-white" aria-hidden="true" />
        <span>{t('registrarPanel.data_source_api')}</span>
        <span className="registrar-ds-count">
          {count} / {paginationInfo?.total ?? count}
        </span>
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
