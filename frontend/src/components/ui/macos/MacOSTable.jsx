import React, { useState } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';

const MacOSTable = ({
  columns = [],
  data = [],
  loading = false,
  emptyState,
  sortable = true,
  selectable = false,
  selectedRows = [],
  onRowSelect,
  onSort,
  size = 'md',
  variant = 'default',
  striped = false,
  hoverable = true,
  className,
  style,
  children // ✅ Добавляем поддержку children для legacy использования
}) => {
  const [sortColumn, setSortColumn] = useState(null);
  const [sortDirection, setSortDirection] = useState('asc');

  const sizeStyles = {
    sm: {
      padding: '8px 12px',
      fontSize: 'var(--mac-font-size-xs)',
      headerPadding: '6px 12px'
    },
    md: {
      padding: '12px 16px',
      fontSize: 'var(--mac-font-size-sm)',
      headerPadding: '10px 16px'
    },
    lg: {
      padding: '16px 20px',
      fontSize: 'var(--mac-font-size-base)',
      headerPadding: '14px 20px'
    }
  };

  const variantStyles = {
    default: {
      border: '1px solid var(--mac-border)',
      background: 'var(--mac-bg-primary)',
      headerBackground: 'var(--mac-bg-tertiary)'
    },
    filled: {
      border: 'none',
      background: 'var(--mac-bg-secondary)',
      headerBackground: 'var(--mac-bg-primary)'
    },
    minimal: {
      border: 'none',
      background: 'transparent',
      headerBackground: 'var(--mac-bg-tertiary)'
    }
  };

  const currentSize = sizeStyles[size];
  const currentVariant = variantStyles[variant];

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse',
    borderRadius: 'var(--mac-radius-md)',
    overflow: 'hidden',
    ...currentVariant,
    ...style
  };

  const headerStyle = {
    background: currentVariant.headerBackground,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    fontSize: currentSize.fontSize,
    padding: currentSize.headerPadding,
    textAlign: 'left',
    borderBottom: '1px solid var(--mac-border)',
    borderRight: '1px solid var(--mac-border)',
    cursor: sortable ? 'pointer' : 'default',
    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
    userSelect: 'none'
  };

  const cellStyle = (isSelected = false) => ({
    padding: currentSize.padding,
    fontSize: currentSize.fontSize,
    color: 'var(--mac-text-primary)',
    borderBottom: '1px solid var(--mac-border)',
    borderRight: '1px solid var(--mac-border)',
    background: isSelected ? 'var(--mac-bg-blue)' : 'transparent',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
  });

  const rowStyle = (index, isSelected = false) => ({
    background: striped && index % 2 === 1 ? 'var(--mac-bg-secondary)' : 'transparent',
    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
    cursor: hoverable ? 'pointer' : 'default'
  });

  const handleSort = (column) => {
    if (!sortable || !column.sortable) return;

    const newDirection = sortColumn === column.key && sortDirection === 'asc' ? 'desc' : 'asc';
    setSortColumn(column.key);
    setSortDirection(newDirection);
    
    if (onSort) {
      onSort(column.key, newDirection);
    }
  };

  const handleRowClick = (row, index) => {
    if (selectable && onRowSelect) {
      onRowSelect(row, index);
    }
  };

  const handleMouseEnter = (e, isSelected) => {
    if (hoverable) {
      e.currentTarget.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'var(--mac-bg-secondary)';
    }
  };

  const handleMouseLeave = (e, isSelected) => {
    if (hoverable) {
      e.currentTarget.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'transparent';
    }
  };

  const renderSortIcon = (column) => {
    if (!sortable || !column.sortable) return null;
    
    const isActive = sortColumn === column.key;
    const isAsc = sortDirection === 'asc';
    
    return (
      <span style={{ marginLeft: '8px', display: 'inline-flex', alignItems: 'center' }}>
        {isActive ? (
          isAsc ? <ChevronUp size={14} /> : <ChevronDown size={14} />
        ) : (
          <span style={{ opacity: 0.3 }}>
            <ChevronUp size={14} />
          </span>
        )}
      </span>
    );
  };

  const renderCell = (row, column, rowIndex) => {
    if (column.render) {
      return column.render(row[column.key], row, rowIndex);
    }
    return row[column.key];
  };

  const renderEmptyState = () => {
    if (emptyState) {
      return emptyState;
    }
    
    return (
      <tr>
        <td 
          colSpan={columns.length} 
          style={{
            padding: '48px 16px',
            textAlign: 'center',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)'
          }}
        >
          Нет данных для отображения
        </td>
      </tr>
    );
  };

  const renderLoadingState = () => {
    return (
      <tr>
        <td 
          colSpan={columns.length} 
          style={{
            padding: '48px 16px',
            textAlign: 'center',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)'
          }}
        >
          Загрузка...
        </td>
      </tr>
    );
  };

  if (loading) {
    return (
      <div style={{ overflowX: 'auto' }}>
        <table className={className} style={tableStyle}>
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th key={column.key || index} style={{
                  ...headerStyle,
                  borderRight: index === columns.length - 1 ? 'none' : '1px solid var(--mac-border)'
                }}>
                  {column.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {renderLoadingState()}
          </tbody>
        </table>
      </div>
    );
  }

  // ✅ Если переданы children, рендерим их напрямую (legacy режим)
  if (children) {
    return (
      <div style={{ overflowX: 'auto' }}>
        <table className={className} style={tableStyle}>
          {children}
        </table>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div style={{ overflowX: 'auto' }}>
        <table className={className} style={tableStyle}>
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th key={column.key || index} style={{
                  ...headerStyle,
                  borderRight: index === columns.length - 1 ? 'none' : '1px solid var(--mac-border)'
                }}>
                  {column.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {renderEmptyState()}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className={className} style={tableStyle}>
        <thead>
          <tr>
            {columns.map((column, index) => (
              <th
                key={column.key || index}
                style={{
                  ...headerStyle,
                  borderRight: index === columns.length - 1 ? 'none' : '1px solid var(--mac-border)'
                }}
                onClick={() => handleSort(column)}
                onMouseEnter={(e) => {
                  if (sortable && column.sortable) {
                    e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (sortable && column.sortable) {
                    e.target.style.backgroundColor = currentVariant.headerBackground;
                  }
                }}
              >
                {column.title}
                {renderSortIcon(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => {
            const isSelected = selectedRows.includes(rowIndex);
            return (
              <tr
                key={rowIndex}
                style={rowStyle(rowIndex, isSelected)}
                onClick={() => handleRowClick(row, rowIndex)}
                onMouseEnter={(e) => handleMouseEnter(e, isSelected)}
                onMouseLeave={(e) => handleMouseLeave(e, isSelected)}
              >
                {columns.map((column, colIndex) => (
                  <td
                    key={column.key || colIndex}
                    style={{
                      ...cellStyle(isSelected),
                      borderRight: colIndex === columns.length - 1 ? 'none' : '1px solid var(--mac-border)'
                    }}
                  >
                    {renderCell(row, column, rowIndex)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default MacOSTable;