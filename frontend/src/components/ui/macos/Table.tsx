// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React from 'react';
import { useState } from 'react';
import PropTypes from 'prop-types';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { useTranslation } from '../../../i18n/useTranslation';

const Table = ({
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
  const [sortColumn, setSortColumn] = useState<unknown>(null);
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
      background: 'color-mix(in srgb, var(--mac-card-bg, var(--mac-bg-primary)), var(--mac-gradient-sidebar, var(--mac-main-shell-bg)) 16%)',
      headerBackground: 'var(--mac-table-header-bg)'
    },
    filled: {
      border: 'none',
      background: 'color-mix(in srgb, var(--mac-card-bg, var(--mac-bg-secondary)), var(--mac-gradient-sidebar, var(--mac-main-shell-bg)) 16%)',
      headerBackground: 'var(--mac-table-header-bg)'
    },
    minimal: {
      border: 'none',
      background: 'transparent',
      headerBackground: 'var(--mac-table-header-bg)'
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
    color: 'var(--mac-table-header-text)',
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
    background: isSelected ? 'var(--mac-bg-blue)' : (striped && index % 2 === 1 ? 'var(--mac-table-row-alt-bg)' : 'transparent'),
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

  const handleMouseEnter = (e, isSelected, isSortable) => {
    if (hoverable || isSortable) {
      const target = e.currentTarget;
      if (isSortable && target.tagName === 'TH') {
        target.style.backgroundColor = 'var(--mac-table-header-hover-bg)';
      } else if (hoverable && target.tagName === 'TR') {
        target.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'var(--mac-table-row-hover-bg)';
      }
    }
  };

  const handleMouseLeave = (e, isSelected, isSortable) => {
    const target = e.currentTarget;
    if (isSortable && target.tagName === 'TH') {
      target.style.backgroundColor = currentVariant.headerBackground;
    } else if (hoverable && target.tagName === 'TR') {
      target.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'transparent';
    }
  };

  const handleHeaderKeyDown = (e, column) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleSort(column);
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

  const renderStatusCell = (content) => (
    <tr>
      <td
        colSpan={columns.length}
        role="status"
        aria-live="polite"
        style={{
          padding: '48px 16px',
          textAlign: 'center',
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-base)'
        }}
      >
        {content}
      </td>
    </tr>
  );

  const renderHeaders = () => (
    <thead>
      <tr>
        {columns.map((column, index) => {
          const isSortable = sortable && column.sortable;
          const isSorted = sortColumn === column.key;
          return (
            <th
              key={column.key || index}
              style={{
                ...headerStyle,
                borderRight: index === columns.length - 1 ? 'none' : '1px solid var(--mac-border)'
              }}
              onClick={() => handleSort(column)}
              onKeyDown={(e) => handleHeaderKeyDown(e, column)}
              tabIndex={isSortable ? 0 : undefined}
              aria-sort={isSortable ? (isSorted ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none') : undefined}
              onMouseEnter={(e) => handleMouseEnter(e, false, isSortable)}
              onMouseLeave={(e) => handleMouseLeave(e, false, isSortable)}
            >
              {column.title}
              {renderSortIcon(column)}
            </th>
          );
        })}
      </tr>
    </thead>
  );

  if (loading) {
    return (
      <div style={{ overflowX: 'auto' }} aria-busy="true">
        <table className={className} style={tableStyle}>
          {renderHeaders()}
          <tbody>
            {renderStatusCell('Загрузка...')}
          </tbody>
        </table>
      </div>
    );
  }

  if (children) {
    return (
      <div style={{ overflowX: 'auto' }} aria-busy={loading}>
        <table className={className} style={tableStyle}>
          {children}
        </table>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div style={{ overflowX: 'auto' }} aria-busy={loading}>
        <table className={className} style={tableStyle}>
          {renderHeaders()}
          <tbody>
            {renderStatusCell(emptyState || 'Нет данных для отображения')}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }} aria-busy={loading}>
      <table className={className} style={tableStyle}>
        {renderHeaders()}
        <tbody>
          {data.map((row, rowIndex) => {
            const isSelected = selectedRows.includes(rowIndex);
            return (
              <tr
                key={rowIndex}
                style={rowStyle(rowIndex, isSelected)}
                onClick={() => handleRowClick(row, rowIndex)}
                onMouseEnter={(e) => handleMouseEnter(e, isSelected, false)}
                onMouseLeave={(e) => handleMouseLeave(e, isSelected, false)}
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

Table.propTypes = {
  columns: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string,
      title: PropTypes.node,
      sortable: PropTypes.bool,
      render: PropTypes.func
    })
  ),
  data: PropTypes.arrayOf(PropTypes.object),
  loading: PropTypes.bool,
  emptyState: PropTypes.node,
  sortable: PropTypes.bool,
  selectable: PropTypes.bool,
  selectedRows: PropTypes.arrayOf(PropTypes.number),
  onRowSelect: PropTypes.func,
  onSort: PropTypes.func,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  variant: PropTypes.oneOf(['default', 'filled', 'minimal']),
  striped: PropTypes.bool,
  hoverable: PropTypes.bool,
  className: PropTypes.string,
  style: PropTypes.object,
  children: PropTypes.node
};

const TableHead = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const headStyles = {
    backgroundColor: 'var(--mac-table-header-bg)',
    borderBottom: '1px solid var(--mac-separator)',
    ...style
  };

  return (
    <thead
      ref={ref}
      className={`mac-table-head ${className}`}
      style={headStyles}
      {...props}>
      
      {children}
    </thead>);

});

/**
 * macOS-style TableBody Component
 */
const TableBody = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <tbody
      ref={ref}
      className={`mac-table-body ${className}`}
      style={style}
      {...props}>
      
      {children}
    </tbody>);

});

/**
 * macOS-style TableRow Component
 */
const TableRow = React.forwardRef(({
  children,
  className = '',
  style = {},
  hover = false,
  selected = false,
  onClick,
  ...props
}, ref) => {
  const rowStyles = {
    borderBottom: '1px solid var(--mac-separator)',
    transition: 'background-color 0.2s ease',
    cursor: onClick ? 'pointer' : 'default',
    backgroundColor: selected ? 'var(--mac-accent-blue)' : 'transparent',
    color: selected ? 'white' : 'var(--mac-text-primary)',
    ...style
  };

  const handleMouseEnter = (e) => {
    if (hover && !selected) {
      e.target.style.backgroundColor = 'var(--mac-table-row-hover-bg)';
    }
  };

  const handleMouseLeave = (e) => {
    if (hover && !selected) {
      e.target.style.backgroundColor = 'transparent';
    }
  };

  return (
    <tr
      ref={ref}
      className={`mac-table-row ${selected ? 'mac-table-row--selected' : ''} ${className}`}
      style={rowStyles}
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}>
      
      {children}
    </tr>);

});

/**
 * macOS-style TableCell Component
 */
const TableCell = React.forwardRef(({
  children,
  className = '',
  style = {},
  align = 'left',
  padding = '12px 16px',
  ...props
}, ref) => {
  const cellStyles = {
    padding,
    textAlign: align,
    borderBottom: '1px solid var(--mac-separator)',
    verticalAlign: 'middle',
    ...style
  };

  return (
    <td
      ref={ref}
      className={`mac-table-cell mac-table-cell--${align} ${className}`}
      style={cellStyles}
      {...props}>
      
      {children}
    </td>);

});

/**
 * macOS-style TableHeaderCell Component
 */
const TableHeaderCell = React.forwardRef(({
  children,
  className = '',
  style = {},
  align = 'left',
  padding = '12px 16px',
  sortable = false,
  sortDirection = null,
  onSort,
  ...props
}, ref) => {
  const headerStyles = {
    padding,
    textAlign: align,
    fontWeight: '600',
    fontSize: '13px',
    color: 'var(--mac-table-header-text)',
    backgroundColor: 'var(--mac-table-header-bg)',
    borderBottom: '1px solid var(--mac-separator)',
    verticalAlign: 'middle',
    cursor: sortable ? 'pointer' : 'default',
    userSelect: 'none',
    ...style
  };

  const handleClick = () => {
    if (sortable && onSort) {
      onSort();
    }
  };

  return (
    <th
      ref={ref}
      className={`mac-table-header-cell mac-table-header-cell--${align} ${sortable ? 'mac-table-header-cell--sortable' : ''} ${className}`}
      style={headerStyles}
      onClick={handleClick}
      {...props}>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {children}
        {sortable &&
        <span style={{ fontSize: '12px', opacity: 0.72 }}>
            {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '↕'}
          </span>
        }
      </div>
    </th>);

});

Table.displayName = 'Table';
TableHead.displayName = 'TableHead';
TableBody.displayName = 'TableBody';
TableRow.displayName = 'TableRow';
TableCell.displayName = 'TableCell';
TableHeaderCell.displayName = 'TableHeaderCell';

Table.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  variant: PropTypes.string
};

TableHead.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

TableBody.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

TableRow.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  hover: PropTypes.bool,
  selected: PropTypes.bool,
  onClick: PropTypes.func
};

TableCell.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  align: PropTypes.string,
  padding: PropTypes.string
};

TableHeaderCell.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  align: PropTypes.string,
  padding: PropTypes.string,
  sortable: PropTypes.bool,
  sortDirection: PropTypes.string,
  onSort: PropTypes.func
};

export default Table;
export { TableHead, TableBody, TableRow, TableCell, TableHeaderCell };

