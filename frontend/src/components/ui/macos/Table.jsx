import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Table Component
 * Implements Apple's Human Interface Guidelines for tables
 */
const Table = React.forwardRef(({
  children,
  className = '',
  style = {},
  variant = 'default',
  ...props
}, ref) => {
  const { theme } = useTheme();

  const tableStyles = {
    width: '100%',
    borderCollapse: 'collapse',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    fontSize: '14px',
    lineHeight: '1.4',
    backgroundColor: 'var(--mac-bg-primary)',
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
    ...style
  };

  return (
    <table
      ref={ref}
      className={`mac-table mac-table--${variant} ${className}`}
      style={tableStyles}
      {...props}
    >
      {children}
    </table>
  );
});

/**
 * macOS-style TableHead Component
 */
const TableHead = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const headStyles = {
    backgroundColor: 'var(--mac-bg-secondary)',
    borderBottom: '1px solid var(--mac-separator)',
    ...style
  };

  return (
    <thead
      ref={ref}
      className={`mac-table-head ${className}`}
      style={headStyles}
      {...props}
    >
      {children}
    </thead>
  );
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
      {...props}
    >
      {children}
    </tbody>
  );
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
      e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
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
      {...props}
    >
      {children}
    </tr>
  );
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
      {...props}
    >
      {children}
    </td>
  );
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
    color: 'var(--mac-text-primary)',
    backgroundColor: 'var(--mac-bg-secondary)',
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
      {...props}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {children}
        {sortable && (
          <span style={{ fontSize: '12px', opacity: 0.6 }}>
            {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '↕'}
          </span>
        )}
      </div>
    </th>
  );
});

Table.displayName = 'Table';
TableHead.displayName = 'TableHead';
TableBody.displayName = 'TableBody';
TableRow.displayName = 'TableRow';
TableCell.displayName = 'TableCell';
TableHeaderCell.displayName = 'TableHeaderCell';

export default Table;
export { TableHead, TableBody, TableRow, TableCell, TableHeaderCell };
