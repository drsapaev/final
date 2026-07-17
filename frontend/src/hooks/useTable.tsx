// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * Улучшенная система таблиц для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import { useState, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';

import { useReducedMotion } from './useEnhancedMediaQuery';
import { Input,
// @ts-expect-error — ui/macos not yet migrated (Phase 4 redo)
// @ts-expect-error — module not yet migrated or path issue
  Checkbox } from '../../ui/macos';

// Хук для управления таблицей
export const useTable = <T extends Record<string, unknown>>(data: T[] = [], options: Record<string, unknown> = {}) => {
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
  const [expandedRows, setExpandedRows] = useState(new Set());
  useReducedMotion();

  // Сортировка данных
  const sortedData = useMemo(() => {
    if (!sortConfig) return data;

    return [...data].sort((a, b) => {
      const aValue = a[(sortConfig as { key?: string; direction?: string } | null)?.key];
      const bValue = b[(sortConfig as { key?: string; direction?: string } | null)?.key];

      if (aValue === bValue) return 0;

      const comparison = aValue < bValue ? -1 : 1;
      return (sortConfig as { key?: string; direction?: string } | null)?.direction === 'desc' ? -comparison : comparison;
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
  const totalPages = Math.ceil(filteredData.length / Number(pageSize));
  const startIndex = (Number(currentPage) - 1) * Number(pageSize);
  const paginatedData = filteredData.slice(startIndex, startIndex + Number(pageSize));

  // Сортировка
  const handleSort = useCallback((key) => {
    setSortConfig((prevConfig) => {
      if (prevConfig && prevConfig?.key === key) {
        return {
          key,
          direction: prevConfig?.direction === 'asc' ? 'desc' : 'asc'
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
          key={column?.key}
          className="table-header-cell"
          style={{
            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
            textAlign: column.align || 'left',
            fontSize: 'var(--mac-font-size-base)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            backgroundColor: 'var(--mac-bg-secondary)',
            borderBottom: '1px solid var(--mac-border)',
            cursor: sortable && column.sortable !== false ? 'pointer' : 'default',
            userSelect: 'none',
            transition: prefersReducedMotion ? 'none' : 'background-color 0.2s ease'
          }}
          onClick={() => sortable && column.sortable !== false && onSort(column?.key)}
          onMouseEnter={(e) => {
            if (sortable && column.sortable !== false && !prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-secondary)';
            }
          }}
          onMouseLeave={(e) => {
            if (!prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-secondary)';
            }
          }}>
          
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
              {column.title || column?.key}
              {sortable && column.sortable !== false && sortConfig && (sortConfig as { key?: string; direction?: string } | null)?.key === column?.key &&
            <span style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                  {(sortConfig as { key?: string; direction?: string } | null)?.direction === 'asc' ? '↑' : '↓'}
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
        backgroundColor: selected ? 'var(--mac-accent-bg)' : 'var(--mac-bg-primary)',
        borderBottom: '1px solid var(--mac-border)',
        cursor: onClick ? 'pointer' : 'default',
        transition: prefersReducedMotion ? 'none' : 'background-color 0.2s ease'
      }}
      onClick={handleClick}
      onMouseEnter={(e) => {
        if (onClick && !prefersReducedMotion) {
          (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-secondary)';
        }
      }}
      onMouseLeave={(e) => {
        if (onClick && !prefersReducedMotion) {
          (e.target as HTMLElement).style.backgroundColor = selected ? 'var(--mac-accent-bg)' : 'var(--mac-bg-primary)';
        }
      }}
      {...props}>
      
      {/* Чекбокс для выбора */}
      {selectable &&
      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', width: '40px' }}>
          <Checkbox aria-label={selected ? 'Deselect table row' : 'Select table row'} checked={selected} onChange={handleSelect} style={{ width: '16px', height: '16px', cursor: 'pointer' }} />
        
        </td>
      }

      {/* Стрелка для разворачивания */}
      {expandable &&
        <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', width: '40px' }}>
          <button
          aria-label={expanded ? 'Collapse table row' : 'Expand table row'}
          onClick={handleExpand}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 'var(--mac-font-size-lg)',
            cursor: 'pointer',
            color: 'var(--mac-text-secondary)',
            padding: 'var(--mac-spacing-1)',
            borderRadius: 'var(--mac-radius-sm)',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (!prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-secondary)';
            }
          }}
          onMouseLeave={(e) => {
            if (!prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'transparent';
            }
          }}>
          
            {expanded ? '▼' : '▶'}
          </button>
        </td>
      }

      {/* Ячейки данных */}
      {columns.map((column) =>
      <td
        key={column?.key}
        className="table-cell"
        style={{
          padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
          textAlign: column.align || 'left',
          fontSize: 'var(--mac-font-size-base)',
          color: 'var(--mac-text-primary)',
          borderBottom: '1px solid var(--mac-border)'
        }}>
        
          {column.render ? column.render(row[column?.key], row) : row[column?.key]}
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
        backgroundColor: 'var(--mac-bg-secondary)',
        borderTop: '1px solid var(--mac-border)'
      }}
      {...props}>
      
      {/* Информация о странице */}
      <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>
        Показано {startItem}-{endItem} из {totalItems} записей
      </div>

      {/* Контролы пагинации */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
        {/* Предыдущая страница */}
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          style={{
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            fontSize: 'var(--mac-font-size-base)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-sm)',
            backgroundColor: currentPage === 1 ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
            color: currentPage === 1 ? 'var(--mac-text-tertiary)' : 'var(--mac-text-primary)',
            cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (currentPage !== 1 && !prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-secondary)';
            }
          }}
          onMouseLeave={(e) => {
            if (currentPage !== 1 && !prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-primary)';
            }
          }}>
          
          ← Назад
        </button>

        {/* Номера страниц */}
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-1)' }}>
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            const pageNumber = Math.max(1, Math.min(totalPages, currentPage - 2 + i));
            return (
              <button
                key={pageNumber}
                onClick={() => onPageChange(pageNumber)}
                style={{
                  padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                  fontSize: 'var(--mac-font-size-base)',
                  fontWeight: pageNumber === currentPage ? '600' : '400',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-sm)',
                  backgroundColor: pageNumber === currentPage ? 'var(--mac-accent-blue)' : 'var(--mac-bg-primary)',
                  color: pageNumber === currentPage ? 'var(--mac-bg-primary)' : 'var(--mac-text-primary)',
                  cursor: 'pointer',
                  minWidth: '40px',
                  transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  if (pageNumber !== currentPage && !prefersReducedMotion) {
                    (e.target as HTMLElement).style.backgroundColor = pageNumber === currentPage ? 'var(--mac-accent-blue-hover)' : 'var(--mac-bg-secondary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (pageNumber !== currentPage && !prefersReducedMotion) {
                    (e.target as HTMLElement).style.backgroundColor = pageNumber === currentPage ? 'var(--mac-accent-blue)' : 'var(--mac-bg-primary)';
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
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            fontSize: 'var(--mac-font-size-base)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-sm)',
            backgroundColor: currentPage === totalPages ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
            color: currentPage === totalPages ? 'var(--mac-text-tertiary)' : 'var(--mac-text-primary)',
            cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (currentPage !== totalPages && !prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-secondary)';
            }
          }}
          onMouseLeave={(e) => {
            if (currentPage !== totalPages && !prefersReducedMotion) {
              (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-primary)';
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
        backgroundColor: 'var(--mac-bg-secondary)',
        borderBottom: '1px solid var(--mac-border)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-3)'
      }}
      {...props}>
      
      <div style={{ fontSize: 'var(--mac-font-size-lg)', color: 'var(--mac-text-secondary)' }}>🔍</div>
      <Input
        type="text"
        aria-label={placeholder || 'Table search'}
        value={searchTerm}
        onChange={(e) => onSearch(e.target.value)}
        placeholder={placeholder}
        style={{
          flex: 1,
          padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
          fontSize: 'var(--mac-font-size-base)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-sm)',
          backgroundColor: 'var(--mac-bg-primary)',
          color: 'var(--mac-text-primary)',
          outline: 'none',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease'
        }}
        onFocus={(e) => {
          if (!prefersReducedMotion) {
            (e.target as HTMLElement).style.borderColor = 'var(--mac-accent-blue)';
          }
        }}
        onBlur={(e) => {
          if (!prefersReducedMotion) {
            (e.target as HTMLElement).style.borderColor = 'var(--mac-border)';
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
}) => {
  useReducedMotion();
  void filterable;
  void onSelectAll;

  return (
    <div
      className={`table ${className}`}
      style={{
        backgroundColor: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border)',
        borderRadius: 'var(--mac-radius-md)',
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
        <div className="admin-table-wrapper">
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
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-base)'
        }}>
        
          Загрузка данных...
        </div>
      }

      {error &&
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: 'var(--mac-error)',
          fontSize: 'var(--mac-font-size-base)'
        }}>
        
          Ошибка загрузки данных: {error}
        </div>
      }

      {!loading && !error && data.length === 0 &&
      <div
        style={{
          padding: '40px',
          textAlign: 'center',
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-base)'
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
