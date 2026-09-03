/**
 * TableSkeleton — animated placeholder rows shown while DataTable data is loading.
 *
 * PR-UI-09a (foundation) — sub-feature file per `docs/UI_REMEDIATION_PLAN.md` §PR-UI-09 line 960.
 * Designed for reuse inside custom DataTable column-config consumers OR as a
 * standalone loading state for host screens that don't render a full DataTable yet.
 *
 * A11y:
 *   - Wrapping `<tbody>` exposes `role="status"` + `aria-live="polite"` + `aria-busy="true"`.
 *   - Each skeleton row is marked `aria-hidden="true"` so screen readers skip placeholder cells.
 *
 * Visual:
 *   - Uses canonical macos CSS variables (`--mac-bg-secondary`, `--mac-border`,
 *     `--mac-radius-md`, `--mac-duration-normal`, `--mac-ease`) — no inline hex colors.
 *   - Inherit row height from `rowHeight` prop (default 48px); consumers may pass
 *     a row height that matches their actual row size for visual continuity.
 *
 * Zero-delta note:
 *   - macos/Table's default `loading` rendering is still the text-only "Загрузка…"
 *     cell (preserved verbatim in canonical DataTable). Consumers that prefer a
 *     skeleton loading state can render `<TableSkeleton />` directly inside
 *     `<DataTable>{children}</DataTable>` slot pattern, or build a dedicated
 *     loading view around it. The text-only default is preserved to keep
 *     existing 13 macos/Table consumers byte-identical (Task 46 §F.2 zero-delta gate).
 */

import React, { type CSSProperties } from 'react';

export interface TableSkeletonProps {
  /** Number of placeholder rows to render. Default: 5. */
  rows?: number;
  /** Number of columns to render per row. Default: 4. */
  columns?: number;
  /** Row height in px. Default: 48. */
  rowHeight?: number;
  /** Extra className for the wrapping `<tbody>`. */
  className?: string;
  /** Inline style override for the wrapping `<tbody>`. */
  style?: CSSProperties;
  /** Accessible label announced by screen readers. Default: "Загрузка данных…". */
  ariaLabel?: string;
}

export const TableSkeleton = ({
  rows = 5,
  columns = 4,
  rowHeight = 48,
  className,
  style,
  ariaLabel = 'Загрузка данных…',
}: TableSkeletonProps): React.ReactElement => {
  return (
    <tbody
      className={`mac-table-skeleton ${className ?? ''}`.trim()}
      style={style}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={ariaLabel}
      data-row-height={rowHeight}
    >
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr
          key={`skeleton-row-${rowIndex}`}
          className="mac-table-skeleton-row"
          aria-hidden="true"
        >
          {Array.from({ length: columns }).map((_, colIndex) => (
            // eslint-disable-next-line jsx-a11y/control-has-associated-label -- skeleton cells are intentionally non-interactive (parent <tr aria-hidden="true"> already hides them from AT)
            <td
              key={`skeleton-cell-${rowIndex}-${colIndex}`}
              className={`mac-table-skeleton-cell ${colIndex === columns - 1 ? 'mac-table-skeleton-cell--last' : ''}`.trim()}
            >
              <span className="mac-table-skeleton-bar" role="presentation" aria-hidden="true" />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
};

TableSkeleton.displayName = 'TableSkeleton';

export default TableSkeleton;
