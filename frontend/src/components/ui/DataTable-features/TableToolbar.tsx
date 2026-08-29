/**
 * TableToolbar — opt-in toolbar for the canonical DataTable (PR-UI-12 item 3).
 *
 * Renders the column-visibility menu and/or the density segmented control.
 * DataTable mounts this component ONLY when `showColumnToggle` or
 * `showDensityToggle` is explicitly set — every existing consumer keeps a
 * byte-identical DOM (zero-delta guarantee, Task 46 §F.2 discipline).
 *
 * State model: fully CONTROLLED by the consumer.
 *   - Column visibility: `columnVisibility` (map) + `onColumnVisibilityChange`.
 *     `columnVisibility?.[key] === false` hides the column; undefined = visible.
 *     Statically `hidden` columns are NOT offered in the menu (not user-togglable).
 *   - Density: `density` + `onDensityChange` (drives the existing DataTable
 *     `density` prop; when `density` is undefined no option is pressed — the
 *     table falls back to its `size` prop).
 *
 * A11y:
 *   - The column-visibility button carries `aria-haspopup` + `aria-expanded`;
 *     the open menu is a `role="group"` labeled via i18n.
 *   - Menu checkboxes are native `<input type="checkbox">` (keyboard reachable,
 *     screen-reader announced); the LAST visible column's checkbox is disabled
 *     so a table can never lose all of its columns.
 *   - The density control is a `role="group"` of buttons with `aria-pressed`.
 *   - The menu closes on Escape and on outside pointerdown; focus stays on the
 *     toggle button (no focus trap needed for a flat checkbox group).
 *   - Labels resolve through the `table.*` i18n namespace (PR-UI-19 pattern,
 *     all 5 locales) — no hardcoded UI strings.
 *
 * Visual:
 *   - All styling lives in `design-system/tokens.css` under `.mac-table-toolbar*`
 *     classes (canonical macos variables WITH fallbacks — ratchet-safe). No
 *     inline styles, no new token files (AGENTS_UI rule 1).
 */

import React, { useEffect, useId, useRef, useState } from 'react';
import { Columns3 } from 'lucide-react';
import { useTranslation } from '@/i18n/useTranslation';
import type { TableDensity } from '../DataTable';

/**
 * Minimal column shape the toolbar needs. `DataTableColumn<Row>` for ANY Row
 * is structurally assignable to this (superset), so the generic DataTable can
 * pass its typed column config without casts (AGENTS_UI: no `as` casts).
 */
export interface TableToolbarColumn {
  key: string;
  title?: React.ReactNode;
  hidden?: boolean;
}

export interface TableToolbarProps {
  /** Full column config (the menu derives its entries; statically `hidden` columns are excluded). */
  columns: TableToolbarColumn[];
  /** Controlled visibility map — `false` hides the column. Undefined key = visible. */
  columnVisibility?: Record<string, boolean>;
  /** Fires with the full next visibility map when a menu checkbox toggles. */
  onColumnVisibilityChange?: (visibility: Record<string, boolean>) => void;
  /** Render the column-visibility menu control. */
  showColumnToggle?: boolean;
  /** Current density (controlled); when undefined no option is pressed. */
  density?: TableDensity;
  /** Fires when the density control picks a new density. */
  onDensityChange?: (density: TableDensity) => void;
  /** Render the density segmented control. */
  showDensityToggle?: boolean;
}

const DENSITY_OPTIONS: Array<{ value: TableDensity; labelKey: string }> = [
  { value: 'compact', labelKey: 'table.density_compact' },
  { value: 'comfortable', labelKey: 'table.density_comfortable' },
  { value: 'spacious', labelKey: 'table.density_spacious' },
];

/**
 * INERT plain-text label for the column menu (Codex P2, PR 2885).
 * Column `title` may be an interactive ReactNode — e.g. the select-all
 * `<Checkbox>` used as a header title by FileManager.tsx / ServiceCatalog.tsx.
 * Rendering such a live control inside the menu item's `<label>` would inject
 * a second interactive checkbox that bulk-selects rows and toggles the
 * surrounding visibility checkbox. The menu therefore renders ONLY string
 * titles; ReactNode titles fall back to the inert column key.
 */
const columnMenuLabel = (column: TableToolbarColumn): string =>
  typeof column.title === 'string' && column.title.length > 0 ? column.title : column.key;

export const TableToolbar = ({
  columns,
  columnVisibility,
  onColumnVisibilityChange,
  showColumnToggle = false,
  density,
  onDensityChange,
  showDensityToggle = false,
}: TableToolbarProps): React.ReactElement => {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRootRef = useRef<HTMLDivElement | null>(null);
  // Codex P2 (PR 2885 round 3): the popup is a `role="group"` of native
  // checkboxes, NOT a menu — `aria-haspopup` would announce the wrong
  // interaction model. Use the disclosure pattern instead: aria-expanded +
  // aria-controls linking the button to the group it toggles.
  const menuId = useId();
  // Codex P2 (PR 2885): Escape must return keyboard focus to the toggle
  // button — the menu unmounts, so focus would otherwise fall back to the
  // document body and the user loses their place.
  const toggleButtonRef = useRef<HTMLButtonElement | null>(null);

  // Close the open menu on outside pointerdown and on Escape (Escape also
  // restores focus to the toggle button).
  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      const root = menuRootRef.current;
      if (root && event.target instanceof Node && !root.contains(event.target)) {
        setMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        toggleButtonRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen]);

  // Statically hidden columns are never offered in the menu.
  const togglableColumns = columns.filter((column) => column.hidden !== true);
  const isColumnVisible = (key: string): boolean => columnVisibility?.[key] !== false;
  const visibleCount = togglableColumns.filter((column) => isColumnVisible(column.key)).length;

  const toggleColumn = (key: string): void => {
    if (!onColumnVisibilityChange) return;
    // Guard: never allow hiding the last visible column.
    if (isColumnVisible(key) && visibleCount <= 1) return;
    onColumnVisibilityChange({ ...columnVisibility, [key]: !isColumnVisible(key) });
  };

  return (
    <div className="mac-table-toolbar">
      {showColumnToggle && (
        <div className="mac-table-toolbar__columns" ref={menuRootRef}>
          <button
            ref={toggleButtonRef}
            type="button"
            className="mac-table-toolbar__button"
            aria-expanded={menuOpen}
            aria-controls={menuId}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Columns3 size={14} aria-hidden="true" />
            <span>{t('table.columns')}</span>
          </button>
          {menuOpen && (
            <div id={menuId} className="mac-table-toolbar__menu" role="group" aria-label={t('table.columns_menu')}>
              {togglableColumns.map((column) => {
                const checked = isColumnVisible(column.key);
                // The last visible column cannot be hidden (a table needs ≥1 column).
                const disabled = checked && visibleCount <= 1;
                return (
                  <label key={column.key} className="mac-table-toolbar__menu-item">
                    <input
                      type="checkbox"
                      aria-label={columnMenuLabel(column)}
                      checked={checked}
                      disabled={disabled}
                      onChange={() => toggleColumn(column.key)}
                    />
                    <span>{columnMenuLabel(column)}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      )}
      {showDensityToggle && (
        <div className="mac-table-toolbar__density" role="group" aria-label={t('table.density')}>
          {DENSITY_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className="mac-table-toolbar__density-option"
              aria-pressed={density === option.value}
              onClick={() => onDensityChange?.(option.value)}
            >
              {t(option.labelKey)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default TableToolbar;
