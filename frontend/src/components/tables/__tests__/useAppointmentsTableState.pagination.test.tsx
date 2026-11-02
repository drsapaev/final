/**
 * REG-FE-051 (registrar audit ledger 3803) — filtered page state.
 *
 * `currentPage` lived independently of the data: navigating to page 3 and
 * then searching a 2-row subset rendered an EMPTY table (the slice started
 * past the matches) while pagination controls were hidden (totalPages <= 1).
 * Contract:
 * - a filter change resets to page 1, so matches are always visible;
 * - a data shrink clamps the page into range even without a filter change;
 * - the hook exposes the clamped page so the selector shows reality.
 */
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAppointmentsTableState } from '../useAppointmentsTableState';

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ colorScheme: 'light' }),
}));

const makeRows = (count: number) =>
  Array.from({ length: count }, (_, i) => ({ id: i + 1, patient_fio: `Пациент ${i + 1}` })) as never[];

describe('useAppointmentsTableState — REG-FE-051 filtered page state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('a search that narrows 45 rows to 2 while on page 3 shows the matches (reset to page 1)', async () => {
    const rows = [
      ...makeRows(43),
      { id: 44, patient_fio: 'Целевой Пациент Один' },
      { id: 45, patient_fio: 'Целевой Пациент Два' },
    ] as never[];
    const { result, rerender } = renderHook(({ data }) => useAppointmentsTableState({ data }), {
      initialProps: { data: rows },
    });

    // Navigate to page 3 (rows 41-60 -> only 41-45 exist).
    act(() => {
      result.current.setCurrentPage(3);
    });
    rerender({ data: rows });
    expect(result.current.currentPage).toBe(3);

    // Search narrows the visible set to the two matching rows.
    act(() => {
      result.current.setFilterConfig({ search: 'Целевой', status: '', dateFrom: '', dateTo: '', doctor: '', department: '' });
    });
    rerender({ data: rows });

    expect(result.current.filteredData).toHaveLength(2);
    expect(result.current.paginatedData).toHaveLength(2);
    expect(result.current.currentPage).toBe(1);
    expect(result.current.totalPages).toBe(1);
  });

  it('a data shrink clamps an out-of-range page even without a filter change', async () => {
    const { result, rerender } = renderHook(({ data }) => useAppointmentsTableState({ data }), {
      initialProps: { data: makeRows(45) },
    });
    act(() => {
      result.current.setCurrentPage(3);
    });
    rerender({ data: makeRows(45) });
    expect(result.current.currentPage).toBe(3);

    // The refresh replaces 45 rows with 2: page 3 no longer exists.
    rerender({ data: makeRows(2) });
    expect(result.current.paginatedData).toHaveLength(2);
    expect(result.current.currentPage).toBe(1);
    expect(result.current.totalPages).toBe(1);
  });

  it('regular navigation still works after the clamp', async () => {
    const { result, rerender } = renderHook(({ data }) => useAppointmentsTableState({ data }), {
      initialProps: { data: makeRows(45) },
    });
    act(() => {
      result.current.setCurrentPage(2);
    });
    rerender({ data: makeRows(45) });
    expect(result.current.currentPage).toBe(2);
    expect(result.current.paginatedData).toHaveLength(20);
  });
});
