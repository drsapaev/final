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

const DataSourceIndicator = memo(({ dataSource, count, paginationInfo, onRetry }) => {
  // QW-03 fix: 'demo' state replaced with 'error' state — no more fake data.
  // DS-3: inline styles replaced with .registrar-ds-* CSS classes
  if (dataSource === 'error') {
    return (
      <div className="registrar-ds-indicator registrar-ds-error">
        <Icon name="exclamationmark.triangle" size="small" className="registrar-text-white" />
        <span>Не удалось загрузить записи. Проверьте подключение к серверу.</span>
        <button
          onClick={() => onRetry?.({ source: 'error_refresh_button', force: true })}
          className="registrar-ds-retry-btn">
          Повторить
        </button>
      </div>
    );
  }

  if (dataSource === 'api') {
    return (
      <div className="registrar-ds-indicator registrar-ds-success">
        <Icon name="checkmark.circle" size="small" className="registrar-text-white" />
        <span>Данные загружены с сервера</span>
        <span className="registrar-ds-count">
          {count} из {paginationInfo?.total ?? count} записей
        </span>
      </div>
    );
  }

  if (dataSource === 'loading') {
    return (
      <div className="registrar-ds-indicator registrar-ds-loading">
        <Icon name="arrow.up.arrow.down" size="small" className="registrar-text-white" />
        <span>Загрузка данных...</span>
      </div>
    );
  }

  return null;
});

DataSourceIndicator.displayName = 'DataSourceIndicator';
DataSourceIndicator.propTypes = {
  count: PropTypes.number.isRequired,
  dataSource: PropTypes.oneOf(['loading', 'api', 'error']),
  paginationInfo: PropTypes.shape({
    total: PropTypes.number,
    hasMore: PropTypes.bool,
  }),
  onRetry: PropTypes.func,
};

export default DataSourceIndicator;
