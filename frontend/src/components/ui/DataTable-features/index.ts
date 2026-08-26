/**
 * DataTable-features barrel — re-exports all sub-feature components.
 *
 * PR-UI-09a (foundation). Consumers can either import directly from the
 * sub-feature files OR use this barrel:
 *
 * ```ts
 * import { TableSkeleton, TableEmpty, TableError, TablePagination } from '@/components/ui/DataTable-features';
 * ```
 */

export { TableSkeleton } from './TableSkeleton';
export type { TableSkeletonProps } from './TableSkeleton';

export { TableEmpty } from './TableEmpty';
export type { TableEmptyProps } from './TableEmpty';

export { TableError } from './TableError';
export type { TableErrorProps } from './TableError';

export { TablePagination } from './TablePagination';
export type { TablePaginationProps } from './TablePagination';
