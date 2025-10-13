import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Table Component
 * Implements Apple's Human Interface Guidelines for data tables
 */
const Table = React.forwardRef(({
  children,
  variant = 'default',
  size = 'default',
  striped = false,
  hoverable = true,
  sortable = false,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { theme } = useTheme();

  const tableStyles = {
    width: '100%',
    borderCollapse: 'collapse',
    border: '1px solid var(--mac-border)',
    borderRadius: '8px',
    overflow: 'hidden',
    backgroundColor: 'var(--mac-bg-primary)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    ...style
  };

  return (
    <div className={`mac-table-wrapper ${className}`} style={{ position: 'relative' }}>
      <table
        ref={ref}
        className={`mac-table ${striped ? 'mac-table--striped' : ''} ${hoverable ? 'mac-table--hoverable' : ''}`}
        style={tableStyles}
        {...props}
      >
        {children}
      </table>

      <style jsx>{`
        .mac-table {
          font-size: 13px;
          line-height: 1.4;
        }

        .mac-table--striped tbody tr:nth-child(even) {
          background-color: var(--mac-bg-secondary);
        }

        .mac-table--hoverable tbody tr:hover {
          background-color: var(--mac-bg-tertiary);
          cursor: pointer;
        }

        .mac-table--hoverable tbody tr:active {
          background-color: var(--mac-bg-quaternary);
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-table {
            border-color: rgba(255, 255, 255, 0.1);
          }

          .mac-table--striped tbody tr:nth-child(even) {
            background-color: rgba(255, 255, 255, 0.02);
          }

          .mac-table--hoverable tbody tr:hover {
            background-color: rgba(255, 255, 255, 0.05);
          }

          .mac-table--hoverable tbody tr:active {
            background-color: rgba(255, 255, 255, 0.08);
          }
        }

        /* High contrast mode */
        @media (prefers-contrast: high) {
          .mac-table {
            border-width: 2px;
          }

          .mac-table--striped tbody tr:nth-child(even) {
            background-color: rgba(0, 0, 0, 0.05);
          }
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          .mac-table--hoverable tbody tr {
            transition: none;
          }
        }
      `}</style>
    </div>
  );
});

Table.displayName = 'macOS Table';

/**
 * macOS-style Table Header Component
 */
export const TableHeader = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <thead
      ref={ref}
      className={`mac-table-header ${className}`}
      style={{
        backgroundColor: 'var(--mac-bg-secondary)',
        borderBottom: '1px solid var(--mac-separator)',
        ...style
      }}
      {...props}
    >
      {children}
    </thead>
  );
});

TableHeader.displayName = 'macOS Table Header';

/**
 * macOS-style Table Body Component
 */
export const TableBody = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <tbody
      ref={ref}
      className={`mac-table-body ${className}`}
      style={{
        backgroundColor: 'var(--mac-bg-primary)',
        ...style
      }}
      {...props}
    >
      {children}
    </tbody>
  );
});

TableBody.displayName = 'macOS Table Body';

/**
 * macOS-style Table Row Component
 */
export const TableRow = React.forwardRef(({
  children,
  variant = 'default',
  hoverable = true,
  selected = false,
  onClick,
  className = '',
  style = {},
  ...props
}, ref) => {
  const rowStyles = {
    borderBottom: '1px solid var(--mac-separator)',
    transition: hoverable ? 'background-color 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'none',
    backgroundColor: selected ? 'var(--mac-bg-tertiary)' : 'transparent',
    cursor: hoverable && onClick ? 'pointer' : 'default',
    ...style
  };

  const handleClick = (e) => {
    if (onClick) {
      onClick(e);
    }
  };

  return (
    <tr
      ref={ref}
      className={`mac-table-row ${selected ? 'mac-table-row--selected' : ''} ${className}`}
      style={rowStyles}
      onClick={handleClick}
      {...props}
    >
      {children}
    </tr>
  );
});

TableRow.displayName = 'macOS Table Row';

/**
 * macOS-style Table Header Cell Component
 */
export const TableHeaderCell = React.forwardRef(({
  children,
  sortable = false,
  sorted = false,
  sortDirection = 'asc',
  onSort,
  className = '',
  style = {},
  ...props
}, ref) => {
  const handleSort = () => {
    if (sortable && onSort) {
      onSort(sortDirection === 'asc' ? 'desc' : 'asc');
    }
  };

  return (
    <th
      ref={ref}
      className={`mac-table-header-cell ${sortable ? 'mac-table-header-cell--sortable' : ''} ${className}`}
      style={{
        padding: '12px 16px',
        textAlign: 'left',
        fontSize: '11px',
        fontWeight: '600',
        color: 'var(--mac-text-secondary)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        borderBottom: '1px solid var(--mac-separator)',
        backgroundColor: 'var(--mac-bg-secondary)',
        position: 'relative',
        userSelect: 'none',
        cursor: sortable ? 'pointer' : 'default',
        ...style
      }}
      onClick={handleSort}
      {...props}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px'
      }}>
        {children}
        {sortable && (
          <svg
            style={{
              width: '12px',
              height: '12px',
              opacity: sorted ? 1 : 0.3,
              transform: sortDirection === 'desc' ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)'
            }}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M7 14l5-5 5 5"/>
          </svg>
        )}
      </div>
    </th>
  );
});

TableHeaderCell.displayName = 'macOS Table Header Cell';

/**
 * macOS-style Table Cell Component
 */
export const TableCell = React.forwardRef(({
  children,
  variant = 'default',
  align = 'left',
  className = '',
  style = {},
  ...props
}, ref) => {
  const cellStyles = {
    padding: '12px 16px',
    textAlign: align,
    fontSize: '13px',
    color: 'var(--mac-text-primary)',
    borderBottom: '1px solid var(--mac-separator)',
    backgroundColor: 'var(--mac-bg-primary)',
    verticalAlign: 'middle',
    ...style
  };

  // Variant styles
  if (variant === 'numeric') {
    cellStyles.fontFamily = 'SF Mono, Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace';
    cellStyles.fontSize = '12px';
  }

  return (
    <td
      ref={ref}
      className={`mac-table-cell ${className}`}
      style={cellStyles}
      {...props}
    >
      {children}
    </td>
  );
});

TableCell.displayName = 'macOS Table Cell';

export default Table;
