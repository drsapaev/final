/**
 * macos/Table.tsx — thin compatibility re-export alias.
 *
 * PR-UI-09a (foundation) per Task 46 §B.3 strategy + Rule 10 compliance.
 *
 * The canonical Table implementation now lives at
 * `src/components/ui/DataTable.tsx`. This file is preserved as a thin
 * re-export alias so existing consumers that import from
 * `../ui/macos` continue to resolve without code changes.
 *
 * ## Migration status
 *
 * - 09a (this PR): alias introduced. Zero-delta for 13 existing consumers
 *   (TelegramManager, EmailSMSManager, RefundRequestsTable, AIAnalytics,
 *   6 admin/* surfaces, FileManager, plus MacOSTable.test.tsx).
 * - 09b–09e (future sub-PRs): consumers are migrated one-by-one to import
 *   directly from `../ui/DataTable`. After the last consumer is migrated,
 *   this alias is removed in a final cleanup PR (per established post-#2841
 *   practice — see AGENTS_UI Rule 12 "sequential migration").
 *
 * ## Zero-delta verification
 *
 * Task 46 §F.2 mandates that visual regression baselines for Surfaces 1, 3, 4
 * continue to PASS after the alias swap. If a snapshot delta appears:
 *   1. Determine the changed region (pixel-diff bbox).
 *   2. Prove causality (which exact line in DataTable.tsx deviates from the
 *      pre-alias macos/Table.tsx rendering).
 *   3. Decide if the delta is expected (intentional feature activation) or
 *      unexpected (regression).
 *   4. Only after steps 1–3: update the baseline with `--update-snapshots`.
 *
 * This is the Rule 13 snapshot policy — see `docs/AGENTS_UI.md` §13.
 *
 * ## Selection API note
 *
 * The legacy `selectedRows: number[]` index-based selection API is replaced
 * by the canonical ID-based API `selectedRows: Set<RowId>` +
 * `onRowSelect(id: RowId, checked: boolean, row?: Row) => void`. This is
 * invisible to existing consumers because per Task 46 §C.1, ZERO of 13
 * macos/Table JSX consumers use the selection props today.
 */

// Re-export the canonical Table + composed primitives. Default re-export
// preserves the existing `import Table from '../ui/macos'` pattern.
export { default } from '../DataTable';
export { TableHead, TableBody, TableRow, TableCell, TableHeaderCell } from '../DataTable';

// Re-export type aliases so legacy `import type { TableColumn, TableProps }`
// statements continue to resolve.
export type {
  DataTableColumn,
  DataTableProps,
  TableColumn,
  TableProps,
  RowId,
  SortDirection,
  TableSize,
  TableVariant,
  TableCellAlign,
  TableDensity,
} from '../DataTable';
