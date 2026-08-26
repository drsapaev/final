/**
 * TablePagination — sticky bottom pagination footer for DataTable.
 *
 * PR-UI-09a (foundation) — sub-feature file per `docs/UI_REMEDIATION_PLAN.md` §PR-UI-09 line 960-964.
 * Reusable pagination control that renders below the `<table>` element. Matches
 * the visual language of the existing `MacOSPagination` component (canonical
 * macos variables + native HTML buttons) so it stays inside the design system.
 *
 * A11y:
 *   - Outer `<nav>` carries `aria-label="Пагинация"` + `role="navigation"`.
 *   - Current page button carries `aria-current="page"` and `aria-disabled="true"`.
 *   - Disabled Previous/Next buttons use `disabled` attribute + `aria-disabled`.
 *
 * Visual:
 *   - Uses canonical macos CSS variables (`--mac-text-primary`,
 *     `--mac-text-secondary`, `--mac-bg-secondary`, `--mac-border`,
 *     `--mac-radius-sm`). No inline hex colors.
 *   - Sticky to bottom of scroll container via `position: sticky; bottom: 0`.
 *
 * Zero-delta note:
 *   - The canonical DataTable does NOT render a pagination footer by default.
 *     macos/Table.tsx's `pagination`/`pageSize`/`onPageChange` props are
 *     stubs with no UI (per Task 46 §B inventory). Consumers that want
 *     pagination can render `<TablePagination />` directly below
 *     `<DataTable>` OR pass `pagination={true}` to the canonical DataTable
 *     (09a wires the prop to render this sub-component additively, only
 *     when explicitly requested).
 */

import React, { type CSSProperties } from 'react';

export interface TablePaginationProps {
  /** Current 1-indexed page. */
  currentPage: number;
  /** Total number of pages. */
  totalPages: number;
  /** Total row count (used for the "Показано X-Y из Z" label). */
  totalItems?: number;
  /** Page size (used for the "Показано X-Y из Z" label). */
  pageSize?: number;
  /** Called when a page button is clicked. */
  onPageChange: (page: number) => void;
  /** Max number of page buttons to render (excluding ellipsis). Default: 7. */
  maxVisiblePages?: number;
  /** Whether to render the "Показано X-Y из Z" summary on the left. Default: true. */
  showSummary?: boolean;
  /** Extra className for the wrapping `<nav>`. */
  className?: string;
  /** Inline style override for the wrapping `<nav>`. */
  style?: CSSProperties;
}

const navBase: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  padding: '8px 12px',
  background: 'var(--mac-table-header-bg)',
  borderTop: '1px solid var(--mac-border)',
  borderBottom: '1px solid var(--mac-border)',
  position: 'sticky',
  bottom: 0,
  zIndex: 1,
};

const buttonBase: CSSProperties = {
  appearance: 'none',
  background: 'transparent',
  border: '1px solid var(--mac-border)',
  borderRadius: 'var(--mac-radius-sm)',
  padding: '4px 10px',
  color: 'var(--mac-text-primary)',
  cursor: 'pointer',
  fontSize: 'var(--mac-font-size-sm)',
  fontFamily: 'inherit',
  minWidth: 28,
  minHeight: 28,
};

const buttonActive: CSSProperties = {
  ...buttonBase,
  background: 'var(--mac-bg-blue)',
  color: 'var(--mac-text-on-accent, white)',
  borderColor: 'var(--mac-bg-blue)',
  cursor: 'default',
};

const buttonDisabled: CSSProperties = {
  ...buttonBase,
  opacity: 0.45,
  cursor: 'not-allowed',
};

/**
 * Build a compact list of page numbers with leading/trailing ellipsis.
 * Example: 1 … 4 5 [6] 7 8 … 12
 */
function buildPageRange(current: number, total: number, maxVisible: number): Array<number | 'ellipsis'> {
  if (total <= maxVisible) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const half = Math.floor(maxVisible / 2);
  const start = Math.max(2, current - half + 1);
  const end = Math.min(total - 1, current + half - 1);
  const range: Array<number | 'ellipsis'> = [1];
  if (start > 2) range.push('ellipsis');
  for (let p = start; p <= end; p++) range.push(p);
  if (end < total - 1) range.push('ellipsis');
  range.push(total);
  return range;
}

export const TablePagination = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize = 10,
  onPageChange,
  maxVisiblePages = 7,
  showSummary = true,
  className,
  style,
}: TablePaginationProps): React.ReactElement | null => {
  if (totalPages <= 1) return null;

  const pages = buildPageRange(currentPage, totalPages, maxVisiblePages);

  const startItem = totalItems != null ? (currentPage - 1) * pageSize + 1 : undefined;
  const endItem = totalItems != null ? Math.min(currentPage * pageSize, totalItems) : undefined;

  const navStyle: CSSProperties = { ...navBase, ...style };

  return (
    <nav
      className={`mac-table-pagination ${className ?? ''}`.trim()}
      style={navStyle}
      aria-label="Пагинация"
      role="navigation"
    >
      {showSummary && totalItems != null ? (
        <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
          Показано {startItem}–{endItem} из {totalItems}
        </div>
      ) : (
        <span />
      )}
      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          aria-disabled={currentPage === 1}
          aria-label="Предыдущая страница"
          style={currentPage === 1 ? buttonDisabled : buttonBase}
        >
          ‹
        </button>
        {pages.map((p, idx) =>
          p === 'ellipsis' ? (
            <span
              key={`ellipsis-${idx}`}
              style={{ padding: '0 4px', color: 'var(--mac-text-secondary)' }}
              aria-hidden="true"
            >
              …
            </span>
          ) : (
            <button
              key={`page-${p}`}
              type="button"
              onClick={() => onPageChange(p)}
              aria-current={p === currentPage ? 'page' : undefined}
              aria-disabled={p === currentPage}
              disabled={p === currentPage}
              style={p === currentPage ? buttonActive : buttonBase}
            >
              {p}
            </button>
          )
        )}
        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          aria-disabled={currentPage === totalPages}
          aria-label="Следующая страница"
          style={currentPage === totalPages ? buttonDisabled : buttonBase}
        >
          ›
        </button>
      </div>
    </nav>
  );
};

TablePagination.displayName = 'TablePagination';

export default TablePagination;
