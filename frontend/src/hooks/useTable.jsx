/**
 * Улучшенная система таблиц для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import { useState, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';

import { useReducedMotion } from './useEnhancedMediaQuery';

// Хук для управления таблицей
export const useTable = (data = [], options = {}) => {
  const {
    pageSize = 10,

    filterable = true,
    searchable = true,



    defaultSort = null,
    defaultFilter = null
  } = options;

  const [currentPage, setCurrentPage] = useState(1);
  const [sortConfig, setSortConfig] = useState(defaultSort);
  const [filterConfig, setFilterConfig] = useState(defaultFilter);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRows, setSelectedRows] = useState(new Set());
  const [expandedRows, setExpandedRows] = useState(new Set());void
  useReducedMotion();

  // Сортировка данных
  const sortedData = useMemo(() => {
    if (!sortConfig) return data;

    return [...data].sort((a, b) => {
      const aValue = a[sortConfig.key];
      const bValue = b[sortConfig.key];

      if (aValue === bValue) return 0;

      const comparison = aValue < bValue ? -1 : 1;
      return sortConfig.direction === 'desc' ? -comparison : comparison;
    });
  }, [data, sortConfig]);

  // Фильтрация данных
  const filteredData = useMemo(() => {
    let filtered = sortedData;

    // Поиск
    if (searchTerm && searchable) {
      filtered = filtered.filter((item) =>
      Object.values(item).some((value) =>
      String(value).toLowerCase().includes(searchTerm.toLowerCase())
      )
      );
    }

    // Фильтры
    if (filterConfig && filterable) {
      Object.entries(filterConfig).forEach(([key, value]) => {
        if (value !== null && value !== undefined && value !== '') {
          filtered = filtered.filter((item) => item[key] === value);
        }
      });
    }

    return filtered;
  }, [sortedData, searchTerm, filterConfig, searchable, filterable]);

  // Пагинация
  const totalPages = Math.ceil(filteredData.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedData = filteredData.slice(startIndex, startIndex + pageSize);

  // Сортировка
  const handleSort = useCallback((key) => {
    setSortConfig((prevConfig) => {
      if (prevConfig && prevConfig.key === key) {
        return {
          key,
          direction: prevConfig.direction === 'asc' ? 'desc' : 'asc'
        };
      }
      return { key, direction: 'asc' };
    });
  }, []);

  // Фильтрация
  const handleFilter = useCallback((key, value) => {
    setFilterConfig((prevConfig) => ({
      ...prevConfig,
      [key]: value
    }));
    setCurrentPage(1); // Сброс на первую страницу при фильтрации
  }, []);

  // Поиск
  const handleSearch = useCallback((term) => {
    setSearchTerm(term);
    setCurrentPage(1); // Сброс на первую страницу при поиске
  }, []);

  // Выбор строк
  const handleRowSelect = useCallback((rowId, selected) => {
    setSelectedRows((prev) => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(rowId);
      } else {
        newSet.delete(rowId);
      }
      return newSet;
    });
  }, []);

  // Выбор всех строк
  const handleSelectAll = useCallback((selected) => {
    if (selected) {
      setSelectedRows(new Set(paginatedData.map((row) => row.id)));
    } else {
      setSelectedRows(new Set());
    }
  }, [paginatedData]);

  // Разворачивание строк
  const handleRowExpand = useCallback((rowId, expanded) => {
    setExpandedRows((prev) => {
      const newSet = new Set(prev);
      if (expanded) {
        newSet.add(rowId);
      } else {
        newSet.delete(rowId);
      }
      return newSet;
    });
  }, []);

  // Сброс всех фильтров и поиска
  const resetFilters = useCallback(() => {
    setSortConfig(defaultSort);
    setFilterConfig(defaultFilter);
    setSearchTerm('');
    setCurrentPage(1);
  }, [defaultSort, defaultFilter]);

  // Получение статистики таблицы
  const getTableStats = useCallback(() => {
    return {
      totalItems: data.length,
      filteredItems: filteredData.length,
      selectedItems: selectedRows.size,
      currentPage,
      totalPages,
      pageSize,
      sortConfig,
      filterConfig,
      searchTerm
    };
  }, [data.length, filteredData.length, selectedRows.size, currentPage, totalPages, pageSize, sortConfig, filterConfig, searchTerm]);

  return {
    // Данные
    data: paginatedData,
    allData: data,
    filteredData,

    // Состояние
    currentPage,
    totalPages,
    sortConfig,
    filterConfig,
    searchTerm,
    selectedRows,
    expandedRows,

    // Действия
    setCurrentPage,
    handleSort,
    handleFilter,
    handleSearch,
    handleRowSelect,
    handleSelectAll,
    handleRowExpand,
    resetFilters,

    // Статистика
    getTableStats
  };
};

// Заголовок таблицы
export const TableHeader = ({
  columns = [],
  sortConfig,
  onSort,
  sortable = true,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  return (
    <thead className={`table-header ${className}`} {...props}>
      <tr>
        {columns.map((column) =>
        <th
          key={column.key}
          className="table-header-cell"
          style={{
            padding: '12px 16px',
            textAlign: column.align || 'left',
            fontSize: '14px',
            fontWeight: '600',
            color: '#374151',
            backgroundColor: '#f9fafb',
            borderBottom: '1px solid #e5e7eb',
            cursor: sortable && column.sortable !== false ? 'pointer' : 'default',
            userSelect: 'none',
            transition: prefersReducedMotion ? 'none' : 'background-color 0.2s ease'
          }}
          onClick={() => sortable && column.sortable !== false && onSort(column.key)}
          onMouseEnter={(e) => {
            if (sortable && column.sortable !== false && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f3f4f6';
            }
          }}
          onMouseLeave={(e) => {
            if (!prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}>
          
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {column.title || column.key}
              {sortable && column.sortable !== false && sortConfig && sortConfig.key === column.key &&
            <span style={{ fontSize: '12px' }}>
                  {sortConfig.direction === 'asc' ? '↑' : '↓'}
                </span>
            }
            </div>
          </th>
        )}
      </tr>
    </thead>);

};

// Строка таблицы
export const TableRow = ({
  row,
  columns = [],
  selected = false,
  expanded = false,
  expandable = false,
  selectable = false,
  onSelect,
  onExpand,
  onClick,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  const handleClick = (e) => {
    if (onClick) {
      onClick(row, e);
    }
  };

  const handleSelect = (e) => {
    e.stopPropagation();
    if (onSelect) {
      onSelect(row.id, !selected);
    }
  };

  const handleExpand = (e) => {
    e.stopPropagation();
    if (onExpand) {
      onExpand(row.id, !expanded);
    }
  };

  return (
    <tr
      className={`table-row ${selected ? 'selected' : ''} ${expanded ? 'expanded' : ''} ${className}`}
      style={{
        backgroundColor: selected ? '#eff6ff' : '#ffffff',
        borderBottom: '1px solid #e5e7eb',
        cursor: onClick ? 'pointer' : 'default',
        transition: prefersReducedMotion ? 'none' : 'background-color 0.2s ease'
      }}
      onClick={handleClick}
      onMouseEnter={(e) => {
        if (onClick && !prefersReducedMotion) {
          e.target.style.backgroundColor = '#f9fafb';
        }
      }}
      onMouseLeave={(e) => {
        if (onClick && !prefersReducedMotion) {
          e.target.style.backgroundColor = selected ? '#eff6ff' : '#ffffff';
        }
      }}
      {...props}>
      
      {/* Чекбокс для выбора */}
      {selectable &&
      <td style={{ padding: '12px 16px', width: '40px' }}>
          <input
          type="checkbox"
          checked={selected}
          onChange={handleSelect}
          style={{
            width: '16px',
            height: '16px',
            cursor: 'pointer'
          }} />
        
        </td>
      }

      {/* Стрелка для разворачивания */}
      {expandable &&
      <td style={{ padding: '12px 16px', width: '40px' }}>
          <button
          onClick={handleExpand}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '16px',
            cursor: 'pointer',
            color: '#6b7280',
            padding: '4px',
            borderRadius: '4px',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (!prefersReducedMotion) {
              e.target.style.backgroundColor = '#f3f4f6';
            }
          }}
          onMouseLeave={(e) => {
            if (!prefersReducedMotion) {
              e.target.style.backgroundColor = 'transparent';
            }
          }}>
          
            {expanded ? '▼' : '▶'}
          </button>
        </td>
      }

      {/* Ячейки данных */}
      {columns.map((column) =>
      <td
        key={column.key}
        className="table-cell"
        style={{
          padding: '12px 16px',
          textAlign: column.align || 'left',
          fontSize: '14px',
          color: '#374151',
          borderBottom: '1px solid #e5e7eb'
        }}>
        
          {column.render ? column.render(row[column.key], row) : row[column.key]}
        </td>
      )}
    </tr>);

};

// Тело таблицы
export const TableBody = ({
  data = [],
  columns = [],
  selectedRows = new Set(),
  expandedRows = new Set(),
  expandable = false,
  selectable = false,
  onRowSelect,
  onRowExpand,
  onRowClick,
  className = '',
  ...props
}) => {
  return (
    <tbody className={`table-body ${className}`} {...props}>
      {data.map((row) =>
      <TableRow
        key={row.id}
        row={row}
        columns={columns}
        selected={selectedRows.has(row.id)}
        expanded={expandedRows.has(row.id)}
        expandable={expandable}
        selectable={selectable}
        onSelect={onRowSelect}
        onExpand={onRowExpand}
        onClick={onRowClick} />

      )}
    </tbody>);

};

// Пагинация таблицы
export const TablePagination = ({
  currentPage,
  totalPages,
  onPageChange,
  pageSize,
  totalItems,
  showPageSize = true,
  pageSizeOptions = [10, 25, 50, 100],
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();
  void showPageSize;
  void pageSizeOptions;

  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  return (
    <div
      className={`table-pagination ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 20px',
        backgroundColor: '#f9fafb',
        borderTop: '1px solid #e5e7eb'
      }}
      {...props}>
      
      {/* Информация о странице */}
      <div style={{ fontSize: '14px', color: '#6b7280' }}>
        Показано {startItem}-{endItem} из {totalItems} записей
      </div>

      {/* Контролы пагинации */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Предыдущая страница */}
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          style={{
            padding: '8px 12px',
            fontSize: '14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            backgroundColor: currentPage === 1 ? '#f3f4f6' : '#ffffff',
            color: currentPage === 1 ? '#9ca3af' : '#374151',
            cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (currentPage !== 1 && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}
          onMouseLeave={(e) => {
            if (currentPage !== 1 && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#ffffff';
            }
          }}>
          
          ← Назад
        </button>

        {/* Номера страниц */}
        <div style={{ display: 'flex', gap: '4px' }}>
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            const pageNumber = Math.max(1, Math.min(totalPages, currentPage - 2 + i));
            return (
              <button
                key={pageNumber}
                onClick={() => onPageChange(pageNumber)}
                style={{
                  padding: '8px 12px',
                  fontSize: '14px',
                  fontWeight: pageNumber === currentPage ? '600' : '400',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  backgroundColor: pageNumber === currentPage ? '#3b82f6' : '#ffffff',
                  color: pageNumber === currentPage ? '#ffffff' : '#374151',
                  cursor: 'pointer',
                  minWidth: '40px',
                  transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  if (pageNumber !== currentPage && !prefersReducedMotion) {
                    e.target.style.backgroundColor = pageNumber === currentPage ? '#2563eb' : '#f9fafb';
                  }
                }}
                onMouseLeave={(e) => {
                  if (pageNumber !== currentPage && !prefersReducedMotion) {
                    e.target.style.backgroundColor = pageNumber === currentPage ? '#3b82f6' : '#ffffff';
                  }
                }}>
                
                {pageNumber}
              </button>);

          })}
        </div>

        {/* Следующая страница */}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          style={{
            padding: '8px 12px',
            fontSize: '14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            backgroundColor: currentPage === totalPages ? '#f3f4f6' : '#ffffff',
            color: currentPage === totalPages ? '#9ca3af' : '#374151',
            cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (currentPage !== totalPages && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}
          onMouseLeave={(e) => {
            if (currentPage !== totalPages && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#ffffff';
            }
          }}>
          
          Далее →
        </button>
      </div>
    </div>);

};

// Поиск в таблице
export const TableSearch = ({
  searchTerm,
  onSearch,
  placeholder = 'Поиск...',
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  return (
    <div
      className={`table-search ${className}`}
      style={{
        padding: '16px 20px',
        backgroundColor: '#f9fafb',
        borderBottom: '1px solid #e5e7eb',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}
      {...props}>
      
      <div style={{ fontSize: '16px', color: '#6b7280' }}>🔍</div>
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => onSearch(e.target.value)}
        placeholder={placeholder}
        style={{
          flex: 1,
          padding: '8px 12px',
          fontSize: '14px',
          border: '1px solid #d1d5db',
          borderRadius: '6px',
          backgroundColor: '#ffffff',
          color: '#374151',
          outline: 'none',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease'
        }}
        onFocus={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = '#3b82f6';
          }
        }}
        onBlur={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = '#d1d5db';
          }
        }} />
      
    </div>);

};

// Полная таблица
export const Table = ({
  data = [],
  columns = [],
  loading = false,
  error = null,
  emptyMessage = 'Нет данных для отображения',

  // Опции таблицы
  sortable = true,
  filterable = true,
  searchable = true,
  selectable = false,
  expandable = false,
  pagination = true,

  // Состояние
  currentPage = 1,
  totalPages = 1,
  sortConfig = null,
  searchTerm = '',

  // Обработчики
  onPageChange,
  onSort,
  onSearch,
  onRowSelect,
  onRowExpand,
  onRowClick,
  onSelectAll,

  // Стиль
  className = '',
  style = {},

  // Размер страницы
  pageSize = 10,
  pageSizeOptions = [10, 25, 50, 100],

  ...props
}) => {void
  useReducedMotion();
  void filterable;
  void onSelectAll;

  return (
    <div
      className={`table ${className}`}
      style={{
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        overflow: 'hidden',
        ...style
      }}
      {...props}>
      
      {/* Поиск */}
      {searchable &&
      <TableSearch
        searchTerm={searchTerm}
        onSearch={onSearch}
        placeholder="Поиск по таблице..." />

      }

      {/* Таблица */}
      <div style={{ overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <TableHeader
            columns={columns}
            sortConfig={sortConfig}
            onSort={onSort}
            sortable={sortable} />
          

          <TableBody
            data={data}
            columns={columns}
            selectedRows={new Set()}
            expandedRows={new Set()}
            selectable={selectable}
            expandable={expandable}
            onRowSelect={onRowSelect}
            onRowExpand={onRowExpand}
            onRowClick={onRowClick} />
          
        </table>
      </div>

      {/* Пагинация */}
      {pagination &&
      <TablePagination
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={onPageChange}
        pageSize={pageSize}
        totalItems={data.length}
        pageSizeOptions={pageSizeOptions} />

      }

      {/* Состояния загрузки и ошибки */}
      {loading &&
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: '#6b7280',
          fontSize: '14px'
        }}>
        
          Загрузка данных...
        </div>
      }

      {error &&
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: '#ef4444',
          fontSize: '14px'
        }}>
        
          Ошибка загрузки данных: {error}
        </div>
      }

      {!loading && !error && data.length === 0 &&
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: '#6b7280',
          fontSize: '14px'
        }}>
        
          {emptyMessage}
        </div>
      }
    </div>);

};

TableHeader.propTypes = {
  columns: PropTypes.array,
  sortConfig: PropTypes.object,
  onSort: PropTypes.func,
  sortable: PropTypes.bool,
  className: PropTypes.string
};

TableRow.propTypes = {
  row: PropTypes.object,
  columns: PropTypes.array,
  selected: PropTypes.bool,
  expanded: PropTypes.bool,
  expandable: PropTypes.bool,
  selectable: PropTypes.bool,
  onSelect: PropTypes.func,
  onExpand: PropTypes.func,
  onClick: PropTypes.func,
  className: PropTypes.string
};

TableBody.propTypes = {
  data: PropTypes.array,
  columns: PropTypes.array,
  selectedRows: PropTypes.instanceOf(Set),
  expandedRows: PropTypes.instanceOf(Set),
  expandable: PropTypes.bool,
  selectable: PropTypes.bool,
  onRowSelect: PropTypes.func,
  onRowExpand: PropTypes.func,
  onRowClick: PropTypes.func,
  className: PropTypes.string
};

TablePagination.propTypes = {
  currentPage: PropTypes.number,
  totalPages: PropTypes.number,
  onPageChange: PropTypes.func,
  pageSize: PropTypes.number,
  totalItems: PropTypes.number,
  showPageSize: PropTypes.bool,
  pageSizeOptions: PropTypes.array,
  className: PropTypes.string
};

TableSearch.propTypes = {
  searchTerm: PropTypes.string,
  onSearch: PropTypes.func,
  placeholder: PropTypes.string,
  className: PropTypes.string
};

Table.propTypes = {
  data: PropTypes.array,
  columns: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.any,
  emptyMessage: PropTypes.string,
  sortable: PropTypes.bool,
  filterable: PropTypes.bool,
  searchable: PropTypes.bool,
  selectable: PropTypes.bool,
  expandable: PropTypes.bool,
  pagination: PropTypes.bool,
  currentPage: PropTypes.number,
  totalPages: PropTypes.number,
  sortConfig: PropTypes.object,
  searchTerm: PropTypes.string,
  onPageChange: PropTypes.func,
  onSort: PropTypes.func,
  onSearch: PropTypes.func,
  onRowSelect: PropTypes.func,
  onRowExpand: PropTypes.func,
  onRowClick: PropTypes.func,
  onSelectAll: PropTypes.func,
  className: PropTypes.string,
  style: PropTypes.object,
  pageSize: PropTypes.number,
  pageSizeOptions: PropTypes.array
};

export default useTable;
