
// Система таблиц с сортировкой, фильтрацией и пагинацией
import PropTypes from 'prop-types';
import { useState, useMemo, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import React, { type CSSProperties, type ReactNode } from "react";

// === Domain types ===
// Table is a generic sortable/filterable/paginated table. Column shape
// covers all variants observed in 19 callers (key, title/header/label,
// render, sortable, width, align, filterable). Row shape is dynamic
// (backend-driven), so it rides along via index signature.

export interface TableColumn {
  /** Unique column key — used as the row[cell.key] accessor. */
  key: string;
  /** Header label (string or ReactNode). */
  title?: ReactNode;
  /** Alias for `title` (used by some callers). */
  header?: string;
  /** Alias for `title` (used by some callers). */
  label?: string;
  /** Custom cell renderer: receives (cellValue, row). */
  render?: (value: unknown, row: Record<string, unknown>) => ReactNode;
  /** Whether this column is sortable (defaults to table-level `sortable`). */
  sortable?: boolean;
  /** Whether this column is filterable (defaults to table-level `filterable`). */
  filterable?: boolean;
  /** Column width (CSS value). */
  width?: string;
  /** Cell text alignment. */
  align?: 'left' | 'right' | 'center' | string;
  [key: string]: unknown;
}

export interface TableProps {
  /** Row data (each row is a dynamic object keyed by column.key). */
  data?: Record<string, unknown>[];
  /** Column definitions. */
  columns?: TableColumn[];
  /** Whether sorting is enabled (per-column overrides via column.sortable). */
  sortable?: boolean;
  /** Whether filtering is enabled (per-column overrides via column.filterable). */
  filterable?: boolean;
  /** Whether pagination is enabled. */
  pagination?: boolean;
  /** Number of rows per page. */
  pageSize?: number;
  /** Sort change handler. */
  onSort?: (field: string, direction: 'asc' | 'desc') => void;
  /** Filter change handler. */
  onFilter?: (field: string, value: string) => void;
  /** Page change handler. */
  onPageChange?: (page: number) => void;
  /** Loading flag — renders skeleton rows when true. */
  loading?: boolean;
  /** Empty-state message. */
  emptyMessage?: string;
  /** Optional empty-state element (overrides emptyMessage). */
  emptyState?: ReactNode;
  /** Optional CSS class. */
  className?: string;
  /** Optional variant. */
  variant?: string;
  /** Optional size. */
  size?: string;
  /** Optional striped rows flag. */
  striped?: boolean;
  /** Optional hoverable rows flag. */
  hoverable?: boolean;
  /** Optional inline style. */
  style?: CSSProperties;
  /** Pass-through props to underlying <table>. */
  [key: string]: unknown;
}

/**
 * Компонент таблицы
 */
export function Table({
  data = [],
  columns = [],
  sortable = true,
  filterable = true,
  pagination = true,
  pageSize = 10,
  onSort,
  onFilter,
  onPageChange,
  loading = false,
  emptyMessage = 'Нет данных',
  ...props
}: TableProps) {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;
  
  const [sortField, setSortField] = useState('');
  const [sortDirection, setSortDirection] = useState('asc');
  const [filters, setFilters] = useState<Record<string, any>>({});
  const [currentPage, setCurrentPage] = useState(1);

  // Сортировка данных
  const sortedData = useMemo(() => {
    if (!sortField || !sortable) return data;
    
    return [...data].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];
      
      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortField, sortDirection, sortable]);

  // Фильтрация данных
  const filteredData = useMemo(() => {
    if (!filterable || Object.keys(filters).length === 0) return sortedData;
    
    return sortedData.filter(item => {
      return Object.entries(filters).every(([key, value]) => {
        if (!value) return true;
        const itemValue = item[key];
        return itemValue?.toString().toLowerCase().includes(value.toLowerCase());
      });
    });
  }, [sortedData, filters, filterable]);

  // Пагинация данных
  const paginatedData = useMemo(() => {
    if (!pagination) return filteredData;
    
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    return filteredData.slice(startIndex, endIndex);
  }, [filteredData, currentPage, pageSize, pagination]);

  // Обработка сортировки
  const handleSort = useCallback((field) => {
    if (!sortable) return;
    
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
    
    onSort?.(field, sortDirection as 'asc' | 'desc');
  }, [sortField, sortDirection, sortable, onSort]);

  // Обработка фильтрации
  const handleFilter = useCallback((field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
    setCurrentPage(1);
    onFilter?.(field, value);
  }, [onFilter]);

  // Обработка изменения страницы
  const handlePageChange = useCallback((page) => {
    setCurrentPage(page);
    onPageChange?.(page);
  }, [onPageChange]);

  const totalPages = Math.ceil(filteredData.length / pageSize);

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse',
    backgroundColor: getColor('background', 'primary'),
    borderRadius: 'var(--mac-radius-md)',
    overflow: 'hidden',
    boxShadow: 'var(--mac-shadow-sm)'
  };

  const headerStyle = {
    backgroundColor: getColor('background', 'secondary'),
    borderBottom: `1px solid ${getColor('border', 'main')}`
  };

  const headerCellStyle = {
    padding: getSpacing('md'),
    textAlign: 'left',
    fontSize: getFontSize('sm'),
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: getColor('text', 'primary'),
    borderBottom: `1px solid ${getColor('border', 'main')}`,
    cursor: sortable ? 'pointer' : 'default',
    userSelect: 'none'
  };

  const cellStyle = {
    padding: getSpacing('md'),
    fontSize: getFontSize('sm'),
    color: getColor('text', 'primary'),
    borderBottom: `1px solid ${getColor('border', 'light')}`
  };

  const rowStyle = {
    transition: 'background-color 0.2s ease'
  };

  const sortIconStyle = {
    marginLeft: getSpacing('xs'),
    fontSize: getFontSize('xs')
  };

  const filterInputStyle = {
    width: '100%',
    padding: getSpacing('xs'),
    fontSize: getFontSize('xs'),
    border: `1px solid ${getColor('border', 'main')}`,
    borderRadius: 'var(--mac-radius-sm)',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary')
  };

  const emptyStyle = {
    textAlign: 'center',
    padding: getSpacing('xl'),
    color: getColor('text', 'secondary'),
    fontSize: getFontSize('md')
  };

  const paginationStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: getSpacing('md'),
    backgroundColor: getColor('background', 'secondary'),
    borderTop: `1px solid ${getColor('border', 'main')}`
  };

  const pageButtonStyle = {
    padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
    margin: `0 ${getSpacing('xs')}`,
    border: `1px solid ${getColor('border', 'main')}`,
    borderRadius: 'var(--mac-radius-sm)',
    backgroundColor: getColor('background', 'primary'),
    color: getColor('text', 'primary'),
    cursor: 'pointer',
    fontSize: getFontSize('sm')
  };

  const activePageButtonStyle = {
    ...pageButtonStyle,
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    borderColor: getColor('primary', 'main')
  };

  const getSortIcon = (field) => {
    if (sortField !== field) return '↕️';
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  if (loading) {
    return <TableLoading columns={columns.length} rows={5} />;
  }

  return (
    <div>
      <div className="admin-table-wrapper">
<table style={tableStyle as CSSProperties} {...props}>
        <thead style={headerStyle as CSSProperties}>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                style={headerCellStyle as CSSProperties}
                onClick={() => handleSort(column.key)}
              >
                {column.title}
                {sortable && (
                  <span style={sortIconStyle as CSSProperties}>
                    {getSortIcon(column.key)}
                  </span>
                )}
              </th>
            ))}
          </tr>
          
          {filterable && (
            <tr>
              {columns.map((column) => (
                <th key={`filter-${column.key}`} style={headerCellStyle as CSSProperties}>
                  {column.filterable !== false && (
                    <Input
                      type="text"
                      aria-label={`Filter ${String(column.title ?? column.header ?? column.label ?? '')}`}
                      placeholder={`Фильтр по ${String(column.title ?? column.header ?? column.label ?? '').toLowerCase()}`}
                      value={filters[column.key] || ''}
                      onChange={(e) => handleFilter(column.key, e.target.value)}
                      style={filterInputStyle as CSSProperties}
                    />
                  )}
                </th>
              ))}
            </tr>
          )}
        </thead>
        
        <tbody>
          {paginatedData.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={emptyStyle as CSSProperties}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            paginatedData.map((row, index) => (
              <tr
                key={String(row.id ?? index)}
                style={rowStyle as CSSProperties}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = getColor('background', 'tertiary');
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                {columns.map((column) => (
                  <td key={column.key} style={cellStyle as CSSProperties}>
                    {column.render ? column.render(row[column.key], row) : String(row[column.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
</div>
      
      {pagination && totalPages > 1 && (
        <div style={paginationStyle as CSSProperties}>
          <div>
            Показано {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, filteredData.length)} из {filteredData.length}
          </div>
          
          <div>
            <button
              style={pageButtonStyle as CSSProperties}
              aria-label="Previous table page"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
            >
              ←
            </button>
            
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const page = i + 1;
              return (
                <button
                  key={page}
                  style={page === currentPage ? activePageButtonStyle : pageButtonStyle}
                  onClick={() => handlePageChange(page)}
                >
                  {page}
                </button>
              );
            })}
            
            <button
              style={pageButtonStyle as CSSProperties}
              aria-label="Next table page"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Компонент загрузки таблицы
 */
function TableLoading({ columns = 3, rows = 5 }) {
  const theme = useTheme();
  const { getColor, getSpacing } = theme;

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse',
    backgroundColor: getColor('background', 'primary'),
    borderRadius: 'var(--mac-radius-md)',
    overflow: 'hidden'
  };

  const cellStyle = {
    padding: getSpacing('md'),
    borderBottom: `1px solid ${getColor('border', 'light')}`
  };

  const skeletonStyle = {
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: 'var(--mac-radius-sm)',
    height: '20px',
    animation: 'skeleton 1.5s ease-in-out infinite'
  };

  return (
    <table style={tableStyle as CSSProperties}>
      <thead>
        <tr>
          {Array.from({ length: columns }).map((_, i) => (
            <th key={i} style={cellStyle as CSSProperties} aria-label={`Loading table column ${i + 1}`}>
              <div style={skeletonStyle as CSSProperties} />
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <tr key={rowIndex}>
            {Array.from({ length: columns }).map((_, colIndex) => (
              <td
                key={colIndex}
                style={cellStyle as CSSProperties}
                aria-label={`Loading table row ${rowIndex + 1} column ${colIndex + 1}`}
              >
                <div style={skeletonStyle as CSSProperties} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Компонент для экспорта таблицы
 */
export function TableExport({ data, columns, filename = 'export.csv' }) {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const handleExport = useCallback(() => {
    const csvContent = [
      columns.map(col => col.title).join(','),
      ...data.map(row => 
        columns.map(col => {
          const value = row[col.key];
          return typeof value === 'string' ? `"${value}"` : value;
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [data, columns, filename]);

  const buttonStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: 'var(--mac-radius-sm)',
    cursor: 'pointer',
    fontSize: getFontSize('sm'),
    fontWeight: 'var(--mac-font-weight-medium)'
  };

  return (
    <button style={buttonStyle as CSSProperties} onClick={handleExport}>
      Экспорт CSV
    </button>
  );
}

const columnShape = PropTypes.shape({
  key: PropTypes.string,
  title: PropTypes.string,
  render: PropTypes.func,
  filterable: PropTypes.bool
});

Table.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  columns: PropTypes.arrayOf(columnShape),
  sortable: PropTypes.bool,
  filterable: PropTypes.bool,
  pagination: PropTypes.bool,
  pageSize: PropTypes.number,
  onSort: PropTypes.func,
  onFilter: PropTypes.func,
  onPageChange: PropTypes.func,
  loading: PropTypes.bool,
  emptyMessage: PropTypes.string
};

TableLoading.propTypes = {
  columns: PropTypes.number,
  rows: PropTypes.number
};

TableExport.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object),
  columns: PropTypes.arrayOf(columnShape),
  filename: PropTypes.string
};

// CSS анимация для скелетона
const style = document.createElement('style');
style.textContent = `
  @keyframes skeleton {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
  }
`;
document.head.appendChild(style);

