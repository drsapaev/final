/**
 * AppointmentPagination — extracted from EnhancedAppointmentsTable.jsx (PR-75).
 *
 * Pagination controls for the appointments table.
 * Previously inline JSX (lines 2490-2590).
 */
import PropTypes from 'prop-types';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';

const AppointmentPagination = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  t,
}) => {
  if (totalItems === 0) return null;

  const start = (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, totalItems);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 'var(--mac-spacing-3)',
      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
      borderTop: '1px solid var(--mac-border)',
    }}>
      <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
        {start}–{end} из {totalItems}
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
        <button
          className="pagination-button"
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          aria-label="Предыдущая страница"
          style={{
            padding: '4px 8px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-sm)',
            background: 'var(--mac-bg-primary)',
            cursor: currentPage <= 1 ? 'default' : 'pointer',
            opacity: currentPage <= 1 ? 0.5 : 1,
          }}
        >
          <ChevronLeft size={16} />
        </button>
        <span style={{ fontSize: 'var(--mac-font-size-sm)', padding: '0 var(--mac-spacing-2)' }}>
          {currentPage} / {totalPages || 1}
        </span>
        <button
          className="pagination-button"
          onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
          disabled={currentPage >= totalPages}
          aria-label="Следующая страница"
          style={{
            padding: '4px 8px',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-sm)',
            background: 'var(--mac-bg-primary)',
            cursor: currentPage >= totalPages ? 'default' : 'pointer',
            opacity: currentPage >= totalPages ? 0.5 : 1,
          }}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
};

AppointmentPagination.propTypes = {
  currentPage: PropTypes.number.isRequired,
  totalPages: PropTypes.number.isRequired,
  totalItems: PropTypes.number.isRequired,
  pageSize: PropTypes.number.isRequired,
  onPageChange: PropTypes.func.isRequired,
  t: PropTypes.object,
};

export default AppointmentPagination;
