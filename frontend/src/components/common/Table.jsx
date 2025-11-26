// Система таблиц с сортировкой, фильтрацией и пагинацией
import React, { useState, useMemo, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

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
}) {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;
  
  const [sortField, setSortField] = useState('');
  const [sortDirection, setSortDirection] = useState('asc');
  const [filters, setFilters] = useState({});
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
    
    onSort?.(field, sortDirection);
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
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
  };

  const headerStyle = {
    backgroundColor: getColor('background', 'secondary'),
    borderBottom: `1px solid ${getColor('border', 'main')}`
  };

  const headerCellStyle = {
    padding: getSpacing('md'),
    textAlign: 'left',
    fontSize: getFontSize('sm'),
    fontWeight: '600',
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
    borderRadius: '4px',
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
    borderRadius: '4px',
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
      <table style={tableStyle} {...props}>
        <thead style={headerStyle}>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                style={headerCellStyle}
                onClick={() => handleSort(column.key)}
              >
                {column.title}
                {sortable && (
                  <span style={sortIconStyle}>
                    {getSortIcon(column.key)}
                  </span>
                )}
              </th>
            ))}
          </tr>
          
          {filterable && (
            <tr>
              {columns.map((column) => (
                <th key={`filter-${column.key}`} style={headerCellStyle}>
                  {column.filterable !== false && (
                    <input
                      type="text"
                      placeholder={`Фильтр по ${column.title.toLowerCase()}`}
                      value={filters[column.key] || ''}
                      onChange={(e) => handleFilter(column.key, e.target.value)}
                      style={filterInputStyle}
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
              <td colSpan={columns.length} style={emptyStyle}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            paginatedData.map((row, index) => (
              <tr
                key={row.id || index}
                style={rowStyle}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = getColor('background', 'tertiary');
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'transparent';
                }}
              >
                {columns.map((column) => (
                  <td key={column.key} style={cellStyle}>
                    {column.render ? column.render(row[column.key], row) : row[column.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      
      {pagination && totalPages > 1 && (
        <div style={paginationStyle}>
          <div>
            Показано {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, filteredData.length)} из {filteredData.length}
          </div>
          
          <div>
            <button
              style={pageButtonStyle}
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
              style={pageButtonStyle}
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
    borderRadius: '8px',
    overflow: 'hidden'
  };

  const cellStyle = {
    padding: getSpacing('md'),
    borderBottom: `1px solid ${getColor('border', 'light')}`
  };

  const skeletonStyle = {
    backgroundColor: getColor('background', 'tertiary'),
    borderRadius: '4px',
    height: '20px',
    animation: 'skeleton 1.5s ease-in-out infinite'
  };

  return (
    <table style={tableStyle}>
      <thead>
        <tr>
          {Array.from({ length: columns }).map((_, i) => (
            <th key={i} style={cellStyle}>
              <div style={skeletonStyle} />
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <tr key={rowIndex}>
            {Array.from({ length: columns }).map((_, colIndex) => (
              <td key={colIndex} style={cellStyle}>
                <div style={skeletonStyle} />
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
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: getFontSize('sm'),
    fontWeight: '500'
  };

  return (
    <button style={buttonStyle} onClick={handleExport}>
      Экспорт CSV
    </button>
  );
}

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

