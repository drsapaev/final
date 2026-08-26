/**
 * TableEmpty — empty-state placeholder for DataTable.
 *
 * PR-UI-09a (foundation) — sub-feature file per `docs/UI_REMEDIATION_PLAN.md` §PR-UI-09 line 960.
 * Reusable empty state that renders inside `<tbody><tr><td>` so the table's
 * column count stays consistent (avoids the validateDOMNesting warnings
 * caught by `MacOSTable.test.tsx` test6 / `DataTable.test.tsx` port).
 *
 * A11y:
 *   - Outer `<td>` carries `role="status"` + `aria-live="polite"` — same
 *     a11y pattern as the canonical DataTable's default empty rendering.
 *   - When `action` (CTA) is provided, it renders as a single button-like
 *     element below the message.
 *
 * Visual:
 *   - Uses canonical macos CSS variables for text/background colors.
 *   - Layout mirrors the existing `AppEmpty` minimal variant to avoid visual
 *     drift (Task 46 §B.2: zero-delta gate for 09a).
 *
 * Zero-delta note:
 *   - The canonical DataTable's default empty rendering is preserved
 *     verbatim (single `<td role="status">` with text or `emptyState` prop).
 *     Consumers that want a richer empty state with a CTA can render
 *     `<TableEmpty />` directly inside `<DataTable>{children}</DataTable>`
 *     slot pattern, or compose it as part of a host-screen loading view.
 */

import React, { type ReactNode, type CSSProperties } from 'react';

export interface TableEmptyProps {
  /** Primary message. Default: "Нет данных для отображения". */
  message?: ReactNode;
  /** Optional secondary description rendered below the message. */
  description?: ReactNode;
  /** Optional CTA element (typically a `<Button>`). Rendered below description. */
  action?: ReactNode;
  /** Optional icon rendered above the message. */
  icon?: ReactNode;
  /** `colSpan` for the wrapping `<td>`. Should equal the number of columns. Default: 1. */
  colSpan?: number;
  /** Extra className for the wrapping `<td>`. */
  className?: string;
  /** Inline style override for the wrapping `<td>`. */
  style?: CSSProperties;
}

export const TableEmpty = ({
  message = 'Нет данных для отображения',
  description,
  action,
  icon,
  colSpan = 1,
  className,
  style,
}: TableEmptyProps): React.ReactElement => {
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
        role="status"
        aria-live="polite"
        className={`mac-table-empty ${className ?? ''}`.trim()}
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
        {action ? (
          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'center' }}>
            {action}
          </div>
        ) : null}
      </td>
    </tr>
  );
};

TableEmpty.displayName = 'TableEmpty';

export default TableEmpty;
