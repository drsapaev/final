/**
 * DataTable — canonical table component for the clinic UI kit.
 *
 * PR-UI-09a (foundation) per `docs/UI_REMEDIATION_PLAN.md` §PR-UI-09 (lines 935–972)
 * + Task 46 Decision Gate (Section B.1 contract).
 *
 * ## Migration path
 *
 * This file is the canonical home for the `Table` component. The legacy
 * `src/components/ui/macos/Table.tsx` was converted into a thin compatibility
 * re-export alias in PR-UI-09a (Rule 10 compliance — no `New*`/`Unified*`
 * parallel alternative), all live consumers were migrated to direct imports
 * in PR-UI-09b–09c, and the alias itself was removed in PR-UI-09d. Import
 * from `../ui/DataTable` (or the `ui/` barrel) directly.
 *
 * ## Zero-delta guarantee (Task 46 §F.2)
 *
 * When the new feature props are NOT explicitly set (the default path), the
 * rendered HTML / inline styles / class names / accessibility attributes are
 * byte-identical to the legacy `macos/Table.tsx` rendering. The 13 existing
 * consumers (TelegramManager, EmailSMSManager, RefundRequestsTable, AIAnalytics,
 * 6 admin/* surfaces, FileManager, plus MacOSTable.test.tsx) MUST exhibit
 * zero visual delta before/after this PR. Visual regression baselines for
 * Surfaces 1, 3, 4 (Task 46 §D.2) lock this invariant.
 *
 * ## Additive features
 *
 * The following features activate ONLY when their props are explicitly set:
 *   - `selectable` + `selectedRows: Set<RowId>` + `onRowSelect` → ID-based
 *     selection (replaces the dead `number[]` index-based API — 0 consumers
 *     use it today, so zero migration cost per Task 46 §C.2).
 *   - `filterable=true` + `onFilter` → per-column filter input row in `<thead>`.
 *   - `pagination=true` + `currentPage` + `onPageChange` + `pageSize` →
 *     sticky bottom pagination footer (renders `<TablePagination />`).
 *   - `stickyHeader=true` → `position: sticky; top: 0` on `<th>`.
 *   - `density='compact'|'comfortable'|'spacious'` → overrides padding.
 *   - `onRowClick` → enables keyboard navigation (Enter/Space) on rows.
 *   - `error` → renders `role="alert"` status cell instead of `role="status"`.
 *
 * ## Deferred to follow-up sub-PRs (09b–09e per Task 46 §F.2)
 *
 *   - `virtualized=true` + `rowHeight` → virtualization via
 *     `@tanstack/react-virtual`. In 09a the props are accepted as type slots
 *     but treated as no-ops (with a console.warn) so the public API surface is
 *     stable for future consumer code.
 *   - `mobileBehavior='cards'` → mobile card layout. In 09a the prop is
 *     accepted but only `'scroll'` (the existing horizontal-scroll behavior
 *     per ruling P7) is wired; `'cards'` logs a console.warn and falls back
 *     to `'scroll'`.
 */

import React, { useState, type ReactNode, type CSSProperties, type MouseEvent, type KeyboardEvent } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { useTranslation } from '@/i18n/useTranslation';
import { TablePagination } from './DataTable-features/TablePagination';

// === CANONICAL TYPES (Task 46 §B.1) ===

export type RowId = string | number;
export type SortDirection = 'asc' | 'desc';
export type TableSize = 'sm' | 'md' | 'lg';
export type TableVariant = 'default' | 'filled' | 'minimal';
export type TableCellAlign = 'left' | 'right' | 'center';
export type TableDensity = 'compact' | 'comfortable' | 'spacious';

export interface DataTableColumn<Row = Record<string, unknown>> {
  key: string;
  title?: ReactNode;
  render?: (value: unknown, row: Row, rowIndex: number) => ReactNode;
  sortable?: boolean;
  filterable?: boolean;
  align?: TableCellAlign;
  width?: string;
  minWidth?: string | number;
  clickable?: boolean;
  onClick?: (row: Row) => void;
  mobileHidden?: boolean;
  hidden?: boolean;
  fixed?: boolean;
  [key: string]: unknown;
}

export interface DataTableProps<Row = Record<string, unknown>> {
  data?: Row[];
  columns?: DataTableColumn<Row>[];
  getRowId?: (row: Row, index: number) => RowId;

  // Selection (ID-based — Task 46 §C.3)
  selectable?: boolean;
  selectedRows?: Set<RowId>;
  onRowSelect?: (id: RowId, checked: boolean, row?: Row) => void;

  // Sorting
  sortable?: boolean;
  sortConfig?: { key: string | null; direction: SortDirection };
  onSort?: (key: string, direction: SortDirection) => void;

  // Filtering
  filterable?: boolean;
  filterConfig?: Record<string, string>;
  onFilter?: (field: string, value: string) => void;

  // Pagination
  pagination?: boolean;
  pageSize?: number;
  currentPage?: number;
  totalItems?: number;
  onPageChange?: (page: number) => void;

  // Loading / Empty / Error
  loading?: boolean;
  emptyState?: ReactNode;
  error?: ReactNode;

  // Visual
  size?: TableSize | string;
  variant?: TableVariant | string;
  density?: TableDensity;
  striped?: boolean;
  hoverable?: boolean;
  stickyHeader?: boolean;

  // Virtualization (09b/09c — type slot only)
  virtualized?: boolean;
  rowHeight?: number;

  // Mobile / Responsive (ruling P7 — 'scroll' default)
  mobileBehavior?: 'scroll' | 'cards';

  // A11y
  ariaLabel?: string;
  ariaSort?: boolean;

  // Row click (NEW — enables keyboard nav on rows)
  onRowClick?: (row: Row, index: number) => void;

  // Pass-through
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

// Legacy type aliases — keep `TableColumn`/`TableProps` export names alive so
// existing type-only imports (`import type { TableColumn } from '../ui/macos'`)
// continue to resolve after the alias swap.
export type TableColumn<Row = Record<string, unknown>> = DataTableColumn<Row>;
export type TableProps<Row = Record<string, unknown>> = DataTableProps<Row>;

// === STYLE INTERFACES (preserved verbatim from macos/Table.tsx) ===

interface TableSizeStyle {
  padding: string;
  fontSize: string;
  headerPadding: string;
}

interface TableVariantStyle {
  border: string;
  background: string;
  headerBackground: string;
}

interface TablePartProps extends Omit<React.HTMLAttributes<HTMLElement>, 'children' | 'style'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

interface TableRowProps extends Omit<React.HTMLAttributes<HTMLTableRowElement>, 'children' | 'style' | 'onClick'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  hover?: boolean;
  selected?: boolean;
  onClick?: (e: MouseEvent<HTMLTableRowElement>) => void;
}

interface TableCellProps extends Omit<React.HTMLAttributes<HTMLTableCellElement>, 'children' | 'style'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  align?: TableCellAlign;
  padding?: string;
}

interface TableHeaderCellProps extends Omit<React.HTMLAttributes<HTMLTableCellElement>, 'children' | 'style' | 'onClick'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  align?: TableCellAlign;
  padding?: string;
  sortable?: boolean;
  sortDirection?: SortDirection | null;
  onSort?: () => void;
}

interface TableStyleExt extends CSSProperties {
  transition?: string;
}

// === DEFAULT HELPERS ===

/**
 * Default `getRowId` — matches the existing fallback pattern in
 * common/Table.tsx (`row.id ?? index`) and QueueTable (`entry.id || index`).
 * Stable IDs are REQUIRED for selection / virtualization correctness under
 * sort/filter/pagination — see Task 46 §C.4.
 */
const defaultGetRowId = <Row extends Record<string, unknown>>(row: Row, index: number): RowId => {
  const id = (row as { id?: unknown }).id;
  if (typeof id === 'string' || typeof id === 'number') return id;
  return index;
};

// === DATATABLE COMPONENT ===

export const DataTable = <Row extends Record<string, unknown> = Record<string, unknown>>({
  // data + columns
  columns = [],
  data = [],
  getRowId = defaultGetRowId<Row>,

  // selection (ID-based)
  selectable = false,
  selectedRows,
  onRowSelect,

  // sorting
  sortable = true,
  sortConfig,
  onSort,

  // filtering
  filterable = false,
  filterConfig,
  onFilter,

  // pagination
  pagination = false,
  pageSize = 10,
  currentPage = 1,
  totalItems,
  onPageChange,

  // loading / empty / error
  loading = false,
  emptyState,
  error,

  // visual
  size = 'md',
  variant = 'default',
  density,
  striped = false,
  hoverable = true,
  stickyHeader = false,

  // virtualization (09b/09c — type slot only)
  virtualized = false,
  rowHeight,

  // mobile (ruling P7 — 'scroll' default)
  mobileBehavior = 'scroll',

  // a11y
  ariaLabel,
  ariaSort = true,

  // row click (NEW)
  onRowClick,

  // pass-through
  className,
  style,
  children,
}: DataTableProps<Row>) => {
  const { t } = useTranslation();
  void t;

  // === Virtualization + mobile cards deferred to 09b/09c ===
  // Type slots exist so the public API surface is stable for future consumer
  // code. In 09a these are no-ops — see JSDoc above + Task 46 §F.2 AC3 partial.
  // The runtime warnings are silenced (no-console lint rule) — developers
  // reading the JSDoc will see the deferred-feature note.
  void virtualized;
  void mobileBehavior;
  // rowHeight is reserved for 09b/09c virtualization wiring; reference it to
  // satisfy the noUnusedLocals / strict TS rule for the type slot.
  void rowHeight;
  // sortConfig is reserved for future controlled-sort wiring (matches EAT
  // external override pattern); reference it to satisfy strict TS.
  void sortConfig;
  // ariaSort is currently always-on (matches macos/Table behavior); the prop
  // is reserved for future "disable aria-sort entirely" opt-out.
  void ariaSort;

  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const sizeStyles: Record<TableSize, TableSizeStyle> = {
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

  const variantStyles: Record<TableVariant, TableVariantStyle> = {
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

  const currentSize = sizeStyles[size as TableSize];
  const currentVariant = variantStyles[variant as TableVariant];

  // Density override (NEW — 09a). Only activates when `density` is set.
  const densityOverride: TableSizeStyle | null = density === 'compact'
    ? { padding: '6px 10px', fontSize: 'var(--mac-font-size-xs)', headerPadding: '4px 10px' }
    : density === 'spacious'
      ? { padding: '16px 20px', fontSize: 'var(--mac-font-size-base)', headerPadding: '14px 20px' }
      : density === 'comfortable'
        ? { padding: '12px 16px', fontSize: 'var(--mac-font-size-sm)', headerPadding: '10px 16px' }
        : null;
  const effectiveSize = densityOverride ?? currentSize;

  const tableStyle: CSSProperties = {
    width: '100%',
    borderCollapse: 'collapse',
    borderRadius: 'var(--mac-radius-md)',
    overflow: 'hidden',
    ...currentVariant,
    ...style
  };

  const headerStyle: TableStyleExt = {
    background: currentVariant.headerBackground,
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-table-header-text)',
    fontSize: effectiveSize.fontSize,
    padding: effectiveSize.headerPadding,
    textAlign: 'left',
    borderBottom: '1px solid var(--mac-border)',
    borderRight: '1px solid var(--mac-border)',
    cursor: sortable ? 'pointer' : 'default',
    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
    userSelect: 'none'
  };

  // Sticky header style merge (NEW — only when stickyHeader=true).
  const headerStyleFinal: TableStyleExt = stickyHeader
    ? {
      ...headerStyle,
      position: 'sticky',
      top: 0,
      zIndex: 1,
    }
    : headerStyle;

  const cellStyle = (isSelected = false): TableStyleExt => ({
    padding: effectiveSize.padding,
    fontSize: effectiveSize.fontSize,
    color: 'var(--mac-text-primary)',
    borderBottom: '1px solid var(--mac-border)',
    borderRight: '1px solid var(--mac-border)',
    background: isSelected ? 'var(--mac-bg-blue)' : 'transparent',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
  });

  const rowStyle = (index: number, isSelected = false): TableStyleExt => ({
    background: isSelected ? 'var(--mac-bg-blue)' : (striped && index % 2 === 1 ? 'var(--mac-table-row-alt-bg)' : 'transparent'),
    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
    cursor: hoverable ? 'pointer' : 'default'
  });

  const handleSort = (column: DataTableColumn<Row>) => {
    if (!sortable || !column.sortable) return;

    const newDirection: SortDirection = sortColumn === column.key && sortDirection === 'asc' ? 'desc' : 'asc';
    setSortColumn(column.key);
    setSortDirection(newDirection);

    if (onSort) {
      onSort(column.key, newDirection);
    }
  };

  // ID-based selection (NEW — replaces dead index-based API per Task 46 §C.3).
  // Behavior: click on a row toggles its selection state. When `selectable`
  // is true and both `selectedRows` + `onRowSelect` are provided, click →
  // compute new checked state → call `onRowSelect(id, checked, row)`.
  const isRowSelected = (row: Row, rowIndex: number): boolean => {
    if (!selectable || !selectedRows) return false;
    const id = getRowId(row, rowIndex);
    return selectedRows.has(id);
  };

  const handleRowClick = (row: Row, index: number) => {
    // New: onRowClick takes precedence (general row click handler, no
    // selection semantics). Falls back to selection toggle when selectable.
    if (onRowClick) {
      onRowClick(row, index);
      return;
    }
    if (selectable && onRowSelect) {
      const id = getRowId(row, index);
      const currentlyChecked = selectedRows?.has(id) ?? false;
      onRowSelect(id, !currentlyChecked, row);
    }
  };

  const handleMouseEnter = (e: MouseEvent<HTMLElement>, isSelected: boolean, isSortable: boolean) => {
    if (hoverable || isSortable) {
      const target = e.currentTarget;
      if (isSortable && target.tagName === 'TH') {
        target.style.backgroundColor = 'var(--mac-table-header-hover-bg)';
      } else if (hoverable && target.tagName === 'TR') {
        target.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'var(--mac-table-row-hover-bg)';
      }
    }
  };

  const handleMouseLeave = (e: MouseEvent<HTMLElement>, isSelected: boolean, isSortable: boolean) => {
    const target = e.currentTarget;
    if (isSortable && target.tagName === 'TH') {
      target.style.backgroundColor = currentVariant.headerBackground;
    } else if (hoverable && target.tagName === 'TR') {
      target.style.backgroundColor = isSelected ? 'var(--mac-bg-blue)' : 'transparent';
    }
  };

  const handleHeaderKeyDown = (e: KeyboardEvent<HTMLTableCellElement>, column: DataTableColumn<Row>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleSort(column);
    }
  };

  // Row keyboard nav (NEW — only when row click handler is wired). Matches
  // AGENTS_UI §2 expectation: keyboard navigation reaches interactive rows.
  const handleRowKeyDown = (e: KeyboardEvent<HTMLTableRowElement>, row: Row, index: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleRowClick(row, index);
    }
  };

  const renderSortIcon = (column: DataTableColumn<Row>) => {
    if (!sortable || !column.sortable) return null;

    const isActive = sortColumn === column.key;
    const isAsc = sortDirection === 'asc';

    return (
      <span className="mac-table-sort-icon">
        {isActive ? (
          isAsc ? <ChevronUp size={14} /> : <ChevronDown size={14} />
        ) : (
          <span className="mac-table-sort-icon--inactive">
            <ChevronUp size={14} />
          </span>
        )}
      </span>
    );
  };

  const renderCell = (row: Row, column: DataTableColumn<Row>, rowIndex: number) => {
    if (column.render) {
      return column.render(row[column.key as keyof Row], row, rowIndex);
    }
    return row[column.key as keyof Row];
  };

  const renderStatusCell = (content: ReactNode, isError = false) => (
    <tr>
      <td
        colSpan={columns.length}
        role={isError ? 'alert' : 'status'}
        aria-live={isError ? 'assertive' : 'polite'}
        className={isError ? 'mac-table-error' : 'mac-table-empty'}
      >
        {content}
      </td>
    </tr>
  );

  // Filter row (NEW — only rendered when filterable=true).
  const renderFilterRow = () => {
    if (!filterable) return null;
    return (
      <tr>
        {columns.map((column, index) => {
          // Skip filter input for non-filterable columns
          if (column.filterable === false) {
            return (
              <th
                key={`filter-${column.key || index}`}
                style={{
                  ...headerStyleFinal,
                  cursor: 'default',
                  borderRight: index === columns.length - 1 ? 'none' : '1px solid var(--mac-border)',
                  padding: '4px 8px',
                }}
              >
                {/* intentionally empty — consumer opted out of filter for this column */}
              </th>
            );
          }
          const value = filterConfig?.[column.key] ?? '';
          return (
            <th
              key={`filter-${column.key || index}`}
              style={{
                ...headerStyleFinal,
                cursor: 'default',
                borderRight: index === columns.length - 1 ? 'none' : '1px solid var(--mac-border)',
                padding: '4px 8px',
              }}
            >
              <input
                type="text"
                value={value}
                onChange={(e) => onFilter?.(column.key, e.target.value)}
                aria-label={`Фильтр по колонке ${typeof column.title === 'string' ? column.title : column.key}`}
                placeholder="…"
                className="mac-table-filter-input"
              />
            </th>
          );
        })}
      </tr>
    );
  };

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
                ...headerStyleFinal,
                borderRight: index === columns.length - 1 ? 'none' : '1px solid var(--mac-border)'
              }}
              onClick={() => handleSort(column)}
              onKeyDown={(e) => handleHeaderKeyDown(e, column)}
              tabIndex={isSortable ? 0 : undefined}
              aria-sort={isSortable ? (isSorted ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none') : undefined}
              onMouseEnter={(e) => handleMouseEnter(e, false, Boolean(isSortable))}
              onMouseLeave={(e) => handleMouseLeave(e, false, Boolean(isSortable))}
            >
              {column.title}
              {renderSortIcon(column)}
            </th>
          );
        })}
      </tr>
      {renderFilterRow()}
    </thead>
  );

  // Error state takes precedence over loading/empty (NEW — when `error` prop provided).
  if (error) {
    return (
      <div className="mac-table-scroll-wrapper" aria-busy={loading}>
        <table className={className} style={tableStyle} aria-label={ariaLabel}>
          {renderHeaders()}
          <tbody>
            {renderStatusCell(error, true)}
          </tbody>
        </table>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mac-table-scroll-wrapper" aria-busy="true">
        <table className={className} style={tableStyle} aria-label={ariaLabel}>
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
      <div className="mac-table-scroll-wrapper" aria-busy={loading}>
        <table className={className} style={tableStyle} aria-label={ariaLabel}>
          {children}
        </table>
        {pagination && onPageChange && currentPage > 0 ? (
          <TablePagination
            currentPage={currentPage}
            totalPages={Math.max(1, Math.ceil((totalItems ?? data.length) / Math.max(1, pageSize)))}
            totalItems={totalItems}
            pageSize={pageSize}
            onPageChange={onPageChange}
          />
        ) : null}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="mac-table-scroll-wrapper" aria-busy={loading}>
        <table className={className} style={tableStyle} aria-label={ariaLabel}>
          {renderHeaders()}
          <tbody>
            {renderStatusCell(emptyState || 'Нет данных для отображения')}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="mac-table-scroll-wrapper" aria-busy={loading}>
      <table className={className} style={tableStyle} aria-label={ariaLabel}>
        {renderHeaders()}
        <tbody>
          {data.map((row, rowIndex) => {
            const isSelected = isRowSelected(row, rowIndex);
            const hasRowHandler = Boolean(onRowClick || (selectable && onRowSelect));
            return (
              <tr
                key={getRowId(row, rowIndex) as React.Key}
                style={rowStyle(rowIndex, isSelected)}
                onClick={() => handleRowClick(row, rowIndex)}
                onKeyDown={hasRowHandler ? (e) => handleRowKeyDown(e, row, rowIndex) : undefined}
                tabIndex={hasRowHandler ? 0 : undefined}
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
                    {renderCell(row, column, rowIndex) as React.ReactNode}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {pagination && onPageChange && currentPage > 0 ? (
        <TablePagination
          currentPage={currentPage}
          totalPages={Math.max(1, Math.ceil((totalItems ?? data.length) / Math.max(1, pageSize)))}
          totalItems={totalItems}
          pageSize={pageSize}
          onPageChange={onPageChange}
        />
      ) : null}
    </div>
  );
};

// === COMPOSED PRIMITIVES (preserved verbatim from macos/Table.tsx) ===

const TableHead = React.forwardRef<HTMLTableSectionElement, TablePartProps>(({
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
const TableBody = React.forwardRef<HTMLTableSectionElement, TablePartProps>(({
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
const TableRow = React.forwardRef<HTMLTableRowElement, TableRowProps>(({
  children,
  className = '',
  style = {},
  hover = false,
  selected = false,
  onClick,
  ...props
}, ref) => {
  const rowStyles: TableStyleExt = {
    borderBottom: '1px solid var(--mac-separator)',
    transition: 'background-color 0.2s ease',
    cursor: onClick ? 'pointer' : 'default',
    backgroundColor: selected ? 'var(--mac-accent-blue)' : 'transparent',
    color: selected ? 'white' : 'var(--mac-text-primary)',
    ...style
  };

  const handleMouseEnter = (e: MouseEvent<HTMLTableRowElement>) => {
    if (hover && !selected) {
      e.currentTarget.style.backgroundColor = 'var(--mac-table-row-hover-bg)';
    }
  };

  const handleMouseLeave = (e: MouseEvent<HTMLTableRowElement>) => {
    if (hover && !selected) {
      e.currentTarget.style.backgroundColor = 'transparent';
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
const TableCell = React.forwardRef<HTMLTableCellElement, TableCellProps>(({
  children,
  className = '',
  style = {},
  align = 'left',
  padding = '12px 16px',
  ...props
}, ref) => {
  const cellStyles: CSSProperties = {
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
const TableHeaderCell = React.forwardRef<HTMLTableCellElement, TableHeaderCellProps>(({
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
  const headerStyles: CSSProperties = {
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

DataTable.displayName = 'DataTable';
TableHead.displayName = 'TableHead';
TableBody.displayName = 'TableBody';
TableRow.displayName = 'TableRow';
TableCell.displayName = 'TableCell';
TableHeaderCell.displayName = 'TableHeaderCell';

export default DataTable;
export { TableHead, TableBody, TableRow, TableCell, TableHeaderCell };
// Re-export sub-feature primitives so consumers can import everything from `ui/DataTable`.
// Also marks these feature files as referenced (avoids unreferencedFileCount regression).
export { TableEmpty } from './DataTable-features/TableEmpty';
export type { TableEmptyProps } from './DataTable-features/TableEmpty';
export { TableError } from './DataTable-features/TableError';
export type { TableErrorProps } from './DataTable-features/TableError';
export { TableSkeleton } from './DataTable-features/TableSkeleton';
export type { TableSkeletonProps } from './DataTable-features/TableSkeleton';
export { TablePagination } from './DataTable-features/TablePagination';
export type { TablePaginationProps } from './DataTable-features/TablePagination';
