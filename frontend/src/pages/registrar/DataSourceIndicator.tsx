/**
 * DataSourceIndicator — inline indicator showing data loading state.
 *
 * UX Audit Registrar #14: extracted from RegistrarPanel.jsx (lines 1283-1328).
 * Pure presentational component, no state — receives dataSource, count,
 * paginationInfo, and loadAppointments as props.
 */

import { memo } from 'react';
import PropTypes from 'prop-types';
import { Icon } from '../../components/ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

interface DataSourceIndicatorProps {
  dataSource?: 'loading' | 'api' | 'error' | string;
  count?: number;
  paginationInfo?: { total?: number; hasMore?: boolean } | null;
  onRetry?: (opts?: Record<string, unknown>) => void;
}

const DataSourceIndicator = memo(({ dataSource, count, paginationInfo, onRetry }: DataSourceIndicatorProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // QW-03 fix: 'demo' state replaced with 'error' state — no more fake data.
  // DS-3: inline styles replaced with .registrar-ds-* CSS classes
  // i18n-unification: hardcoded Russian strings migrated to registrarPanel.* namespace
  if (dataSource === 'error') {
    return (
      <div className="registrar-ds-indicator registrar-ds-error">
        <Icon name="exclamationmark.triangle" size="small" className="registrar-text-white" />
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
        <Icon name="checkmark.circle" size="small" className="registrar-text-white" />
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
        <Icon name="arrow.up.arrow.down" size="small" className="registrar-text-white" />
        <span>{t('registrarPanel.loading')}</span>
      </div>
    );
  }

  return null;
});

DataSourceIndicator.displayName = 'DataSourceIndicator';
(DataSourceIndicator as unknown as { propTypes: unknown }).propTypes = {
  count: PropTypes.number.isRequired,
  dataSource: PropTypes.oneOf(['loading', 'api', 'error']),
  paginationInfo: PropTypes.shape({
    total: PropTypes.number,
    hasMore: PropTypes.bool,
  }),
  onRetry: PropTypes.func,
};

export default DataSourceIndicator;
