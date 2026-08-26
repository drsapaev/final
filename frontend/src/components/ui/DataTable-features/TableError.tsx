/**
 * TableError — error-state placeholder for DataTable.
 *
 * PR-UI-09a (foundation) — sub-feature file per `docs/UI_REMEDIATION_PLAN.md` §PR-UI-09 line 960.
 * Reusable error state that renders inside `<tbody><tr><td>` so the table's
 * column count stays consistent.
 *
 * A11y:
 *   - Outer `<td>` carries `role="alert"` + `aria-live="assertive"` so
 *     screen readers announce the error immediately.
 *   - Error text uses `aria-describedby` to point to the optional `errorId`
 *     element when `errorId` prop is provided (lets consumer reference
 *     a longer error description rendered elsewhere on the page).
 *
 * Visual:
 *   - Uses canonical macos CSS variables (`--mac-text-secondary`,
 *     `--mac-radius-md`, `--mac-border`). No inline hex colors.
 *   - The "retry" affordance is rendered as a button-like element when
 *     `onRetry` callback is provided; the icon is optional.
 *
 * Zero-delta note:
 *   - The canonical DataTable's default rendering has NO `error` rendering
 *     (macos/Table.tsx never had an error state — see Task 46 §B inventory).
 *     Consumers that want an in-table error state can pass `error={<TableError …/>}`
 *     via the slot pattern OR render `<TableError />` directly inside
 *     `<DataTable>{children}</DataTable>`. The existing macos/Table consumers
 *     wrap errors at the host-screen level (AppError), so zero-delta is preserved.
 */

import React, { type ReactNode, type CSSProperties, type MouseEvent } from 'react';

export interface TableErrorProps {
  /** Error message. Default: "Ошибка загрузки данных". */
  message?: ReactNode;
  /** Optional secondary description (e.g. error code / correlation id). */
  description?: ReactNode;
  /** Optional retry CTA. When provided, renders as a button. */
  retryLabel?: ReactNode;
  /** Click handler for the retry button. */
  onRetry?: () => void;
  /** Optional icon rendered above the message. */
  icon?: ReactNode;
  /** `colSpan` for the wrapping `<td>`. Should equal the number of columns. Default: 1. */
  colSpan?: number;
  /** Optional element id to associate via `aria-describedby`. */
  errorId?: string;
  /** Extra className for the wrapping `<td>`. */
  className?: string;
  /** Inline style override for the wrapping `<td>`. */
  style?: CSSProperties;
}

const handleRetryClick = (onRetry?: () => void) => (e: MouseEvent<HTMLButtonElement>) => {
  e.preventDefault();
  e.stopPropagation();
  onRetry?.();
};

export const TableError = ({
  message = 'Ошибка загрузки данных',
  description,
  retryLabel = 'Повторить',
  onRetry,
  icon,
  colSpan = 1,
  errorId,
  className,
  style,
}: TableErrorProps): React.ReactElement => {
  const tdStyle: CSSProperties = {
    padding: '48px 16px',
    textAlign: 'center',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-base)',
    ...style,
  };

  return (
    <tr>
      <td
        colSpan={colSpan}
        role="alert"
        aria-live="assertive"
        aria-describedby={errorId}
        className={`mac-table-error ${className ?? ''}`.trim()}
        style={tdStyle}
      >
        {icon ? (
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}>
            {icon}
          </div>
        ) : null}
        <div>{message}</div>
        {description ? (
          <div style={{ marginTop: 4, fontSize: 'var(--mac-font-size-sm)', opacity: 0.8 }}>
            {description}
          </div>
        ) : null}
        {onRetry ? (
          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={handleRetryClick(onRetry)}
              style={{
                appearance: 'none',
                background: 'transparent',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-sm)',
                padding: '6px 14px',
                color: 'var(--mac-text-primary)',
                cursor: 'pointer',
                fontSize: 'var(--mac-font-size-sm)',
                fontFamily: 'inherit',
              }}
            >
              {retryLabel}
            </button>
          </div>
        ) : null}
      </td>
    </tr>
  );
};

TableError.displayName = 'TableError';

export default TableError;
