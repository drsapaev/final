/**
 * PR-UI-14-1 unit contract: useCashierWorklistData — the cashier data
 * lifecycle slice (fetch effects + pagination + refresh lifecycle) moved
 * verbatim from CashierPanel.
 *
 * Pins the externally observable load semantics that previously lived inline
 * in CashierPanel effects:
 *  - stats load: success sets snapshot; initial failure keeps the legacy
 *    empty snapshot + sets statsError; a refresh failure keeps the previous
 *    snapshot (CSH-FE-001 — zeros are never presented as server-confirmed)
 *  - pending/history loads: success maps data + pagination (or falls back
 *    to totalPages=1 / totalItems=data.length); failure keeps the previous
 *    rows and exposes the section error (CSH-FE-001 — a failed read is not
 *    a confirmed empty)
 *  - out-of-order responses are dropped: only the latest request per
 *    section may write rows/metadata/loading (CSH-FE-002 epoch guard)
 *  - status='all' is NOT sent to the API; specific statuses are passed through
 *  - debounced search is passed through as `search`
 *  - date mode 'single' sends selectedDate for both bounds; 'range' sends from/to
 *  - triggerDataReload resets both pages + bumps refreshKey (all three reload)
 *  - bumpRefreshKey bumps refreshKey only (no page resets)
 *  - changing date inputs resets both pages to 1
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useCashierWorklistData } from '../useCashierWorklistData';
import type { UsePaymentsReturn } from '../../../hooks/usePayments';

type Getters = Pick<UsePaymentsReturn, 'getStats' | 'getPendingPayments' | 'getPayments'>;

interface Harness {
  getStats: ReturnType<typeof vi.fn>;
  getPendingPayments: ReturnType<typeof vi.fn>;
  getPayments: ReturnType<typeof vi.fn>;
}

const makeApi = (): Harness => ({
  getStats: vi.fn(),
  getPendingPayments: vi.fn(),
  getPayments: vi.fn(),
});

const DEFAULT_PROPS = {
  search: '',
  status: 'all',
  dateMode: 'single',
  selectedDate: '2026-08-30',
  dateFrom: '2026-08-01',
  dateTo: '2026-08-30',
};

const renderWorklist = (
  api: Harness,
  overrides: Partial<typeof DEFAULT_PROPS> = {},
) =>
  renderHook(
    (props: typeof DEFAULT_PROPS) =>
      useCashierWorklistData({ ...props, paymentsApi: api as unknown as Getters }),
    { initialProps: { ...DEFAULT_PROPS, ...overrides } },
  );

describe('useCashierWorklistData (PR-UI-14-1)', () => {
  it('loads stats, pending and history on mount and maps results verbatim', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({
      success: true,
      data: { total_amount: 100, cash_amount: 60, card_amount: 40, pending_count: 2, pending_amount: 25, paid_count: 3, cancelled_count: 1 },
    });
    api.getPendingPayments.mockResolvedValue({
      success: true,
      data: [{ id: 11 }, { id: 12 }],
      pagination: { total: 7, page: 1, size: 20, pages: 1 },
    });
    api.getPayments.mockResolvedValue({
      success: true,
      data: [{ id: 'p1' }],
      pagination: { total: 41, page: 1, size: 20, pages: 3 },
    });

    const { result } = renderWorklist(api);

    await waitFor(() => {
      expect(result.current.stats.total_amount).toBe(100);
      expect(result.current.appointments).toHaveLength(2);
      expect(result.current.payments).toEqual([{ id: 'p1' }]);
    });
    expect(result.current.pendingTotalItems).toBe(7);
    expect(result.current.totalPages).toBe(3);
    expect(result.current.totalItems).toBe(41);
    expect(result.current.pendingLoading).toBe(false);
    expect(result.current.historyLoading).toBe(false);
  });

  it('does not invent zeros for CSH-FE-036 fields when the API predates them (P2 4439005298)', async () => {
    const api = makeApi();
    // Old /cashier/stats payload: gross counters only, no refunded/net keys.
    api.getStats.mockResolvedValue({
      success: true,
      data: { total_amount: 100000, cash_amount: 60000, card_amount: 40000, pending_count: 2, pending_amount: 25000, paid_count: 3, cancelled_count: 0 },
    });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    const { result } = renderWorklist(api);

    await waitFor(() => expect(result.current.stats.total_amount).toBe(100000));
    // The snapshot must preserve "field absent": a fake 0 here would render
    // as «0 сум» in CashierStatsCard while the old API never reported it.
    expect(result.current.stats.refunded_amount).toBeUndefined();
    expect(result.current.stats.net_total_amount).toBeUndefined();
    expect(result.current.stats.net_cash_amount).toBeUndefined();
    expect(result.current.stats.net_card_amount).toBeUndefined();
  });

  it('single date mode sends selectedDate as both bounds', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    renderWorklist(api, { dateMode: 'single', selectedDate: '2026-08-15' });

    await waitFor(() => expect(api.getStats).toHaveBeenCalled());
    expect(api.getStats).toHaveBeenCalledWith({ date_from: '2026-08-15', date_to: '2026-08-15' });
    expect(api.getPendingPayments).toHaveBeenCalledWith(expect.objectContaining({
      date_from: '2026-08-15',
      date_to: '2026-08-15',
      page: 1,
      size: 20,
    }));
  });

  it('range date mode sends from/to bounds', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    renderWorklist(api, { dateMode: 'range', dateFrom: '2026-08-01', dateTo: '2026-08-20' });

    await waitFor(() => expect(api.getStats).toHaveBeenCalled());
    expect(api.getStats).toHaveBeenCalledWith({ date_from: '2026-08-01', date_to: '2026-08-20' });
  });

  it('status is not sent when all; specific status passes through; search passes through', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    renderWorklist(api, { status: 'refunded', search: 'Иванов' });

    await waitFor(() => expect(api.getPayments).toHaveBeenCalled());
    expect(api.getPayments).toHaveBeenCalledWith(expect.objectContaining({
      status: 'refunded',
      search: 'Иванов',
    }));
  });

  it('status is not sent to the payments API when value is all', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    renderWorklist(api);

    await waitFor(() => expect(api.getPayments).toHaveBeenCalled());
    expect(api.getPayments).toHaveBeenCalledWith(expect.objectContaining({ status: undefined }));
  });

  it('initial failure keeps empty rows + exposes section errors — never a confirmed empty (CSH-FE-001)', async () => {
    const api = makeApi();
    api.getStats.mockRejectedValue(new Error('boom'));
    api.getPendingPayments.mockResolvedValue({ success: false, data: [], error: 'backend down', pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockRejectedValue(new Error('boom'));

    const { result } = renderWorklist(api);

    await waitFor(() => {
      // CSH-FE-036 P2 (review 4439005298): the empty snapshot keeps the
      // LEGACY zeros (gross tiles unchanged), but the net-of-refunds fields
      // stay ABSENT — their value is unknown, and the card renders «—»
      // instead of inventing a zero.
      expect(result.current.stats).toEqual({
        total_amount: 0, cash_amount: 0, card_amount: 0,
        pending_count: 0, pending_amount: 0, paid_count: 0, cancelled_count: 0,
      });
      expect(result.current.stats.refunded_amount).toBeUndefined();
      expect(result.current.stats.net_total_amount).toBeUndefined();
    });
    await waitFor(() => {
      expect(result.current.appointments).toEqual([]);
      expect(result.current.payments).toEqual([]);
      expect(result.current.pendingLoading).toBe(false);
      expect(result.current.historyLoading).toBe(false);
    });
    // CSH-FE-001: a failed read is NOT a confirmed empty — the hook must
    // expose the failure so the views render error/retry instead of the
    // genuine «no pending payments» / «empty history» empty states.
    expect(result.current.pendingError).toBe('backend down');
    expect(result.current.historyError).toBe('boom');
    expect(result.current.statsError).toBe('boom');
  });

  it('history result without pagination falls back to totalPages=1 and data length', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [{ id: 1 }, { id: 2 }, { id: 3 }] });

    const { result } = renderWorklist(api);

    await waitFor(() => expect(result.current.payments).toHaveLength(3));
    expect(result.current.totalPages).toBe(1);
    expect(result.current.totalItems).toBe(3);
  });

  it('triggerDataReload resets both pages and reloads every section', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    const { result } = renderWorklist(api);
    await waitFor(() => expect(api.getStats).toHaveBeenCalledTimes(1));

    act(() => {
      result.current.setCurrentPage(4);
      result.current.setPendingPage(2);
    });

    act(() => {
      result.current.triggerDataReload();
    });

    await waitFor(() => expect(api.getStats).toHaveBeenCalledTimes(2));
    expect(result.current.currentPage).toBe(1);
    expect(result.current.pendingPage).toBe(1);
  });

  it('bumpRefreshKey reloads without resetting pages', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    const { result } = renderWorklist(api);
    await waitFor(() => expect(api.getStats).toHaveBeenCalledTimes(1));

    act(() => {
      result.current.setCurrentPage(5);
    });
    act(() => {
      result.current.bumpRefreshKey();
    });

    await waitFor(() => expect(api.getStats).toHaveBeenCalledTimes(2));
    expect(result.current.currentPage).toBe(5);
    expect(api.getPayments).toHaveBeenCalledWith(expect.objectContaining({ page: 5 }));
  });

  it('changing date inputs resets both pages to 1', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: { total: 0, page: 1, size: 20, pages: 1 } });

    const { result, rerender } = renderWorklist(api);
    await waitFor(() => expect(api.getStats).toHaveBeenCalledTimes(1));

    act(() => {
      result.current.setCurrentPage(3);
      result.current.setPendingPage(3);
    });

    rerender({ ...DEFAULT_PROPS, selectedDate: '2026-08-29' });

    await waitFor(() => {
      expect(result.current.currentPage).toBe(1);
      expect(result.current.pendingPage).toBe(1);
    });
  });
});

// CSH-FE-002 (out-of-order reads) + CSH-FE-001 (failure truthfulness).
// Fail-first proven on the pre-fix source: every effect wrote its result
// unconditionally after `await`, so a slow response for a superseded
// date/search/page overwrote the newer one, and any failure cleared the
// rows to [] — presented by the views as a server-confirmed empty list.
describe('useCashierWorklistData — CSH-FE-001/002 read integrity', () => {
  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
  };

  const okPending = (ids: number[]) => ({
    success: true,
    data: ids.map((id) => ({ id })),
    pagination: { total: ids.length, page: 1, size: 20, pages: 1 },
  });
  const okHistory = (ids: string[]) => ({
    success: true,
    data: ids.map((id) => ({ id })),
    pagination: { total: ids.length, page: 1, size: 20, pages: 1 },
  });
  const okStats = (total: number) => ({
    success: true,
    data: { total_amount: total, cash_amount: 0, card_amount: total, pending_count: 0, pending_amount: 0, paid_count: 1, cancelled_count: 0 },
  });
  const emptyPagination = { total: 0, page: 1, size: 20, pages: 1 };

  it('drops a late pending response for a superseded date (CSH-FE-002)', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    const a = deferred<unknown>();
    const b = deferred<unknown>();
    api.getPendingPayments.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: emptyPagination });

    const { result, rerender } = renderWorklist(api);

    // Date A -> B: B's request must own the pending section from now on.
    rerender({ ...DEFAULT_PROPS, selectedDate: '2026-09-15' });

    await act(async () => { b.resolve(okPending([21])); });
    await waitFor(() => expect(result.current.appointments).toEqual([{ id: 21 }]));
    expect(result.current.pendingLoading).toBe(false);

    // The OLD date's response lands after the new one — it must be dropped.
    await act(async () => { a.resolve(okPending([11])); });
    await act(async () => { await Promise.resolve(); });
    expect(result.current.appointments).toEqual([{ id: 21 }]);
    expect(result.current.pendingLoading).toBe(false);
  });

  it('drops a late history response for a superseded date (CSH-FE-002)', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: emptyPagination });
    const a = deferred<unknown>();
    const b = deferred<unknown>();
    api.getPayments.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);

    const { result, rerender } = renderWorklist(api);

    rerender({ ...DEFAULT_PROPS, selectedDate: '2026-09-15' });

    await act(async () => { b.resolve(okHistory(['pB'])); });
    await waitFor(() => expect(result.current.payments).toEqual([{ id: 'pB' }]));

    await act(async () => { a.resolve(okHistory(['pA'])); });
    await act(async () => { await Promise.resolve(); });
    expect(result.current.payments).toEqual([{ id: 'pB' }]);
    expect(result.current.historyLoading).toBe(false);
  });

  it('drops a late stats response for a superseded date (CSH-FE-002)', async () => {
    const api = makeApi();
    const a = deferred<unknown>();
    const b = deferred<unknown>();
    api.getStats.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
    api.getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: emptyPagination });
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: emptyPagination });

    const { result, rerender } = renderWorklist(api);

    rerender({ ...DEFAULT_PROPS, selectedDate: '2026-09-15' });

    await act(async () => { b.resolve(okStats(200)); });
    await waitFor(() => expect(result.current.stats.total_amount).toBe(200));

    await act(async () => { a.resolve(okStats(100)); });
    await act(async () => { await Promise.resolve(); });
    expect(result.current.stats.total_amount).toBe(200);
  });

  it('keeps previously loaded rows and raises the section error when a refresh fails (CSH-FE-001)', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    api.getPendingPayments
      .mockResolvedValueOnce(okPending([1, 2]))
      .mockResolvedValueOnce({ success: false, data: [], error: 'backend down' });
    api.getPayments
      .mockResolvedValueOnce(okHistory(['p1']))
      .mockRejectedValueOnce(new Error('boom'));

    const { result } = renderWorklist(api);
    await waitFor(() => {
      expect(result.current.appointments).toHaveLength(2);
      expect(result.current.payments).toEqual([{ id: 'p1' }]);
    });

    act(() => { result.current.bumpRefreshKey(); });

    await waitFor(() => {
      expect(result.current.pendingError).toBe('backend down');
      expect(result.current.historyError).toBe('boom');
      expect(result.current.pendingLoading).toBe(false);
      expect(result.current.historyLoading).toBe(false);
    });
    // The previously loaded rows must survive the failed refresh —
    // clearing them would present a server outage as «no pending payments».
    expect(result.current.appointments).toHaveLength(2);
    expect(result.current.payments).toEqual([{ id: 'p1' }]);
  });

  it('a superseded request failure does not raise an error or clear the newer result (CSH-FE-002)', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    const a = deferred<unknown>();
    api.getPendingPayments.mockReturnValueOnce(a.promise).mockResolvedValueOnce(okPending([31]));
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: emptyPagination });

    const { result, rerender } = renderWorklist(api);

    rerender({ ...DEFAULT_PROPS, selectedDate: '2026-09-15' });

    await waitFor(() => expect(result.current.appointments).toEqual([{ id: 31 }]));

    await act(async () => { a.reject(new Error('late network failure')); });
    await act(async () => { await Promise.resolve(); });

    expect(result.current.appointments).toEqual([{ id: 31 }]);
    expect(result.current.pendingError).toBeNull();
    expect(result.current.pendingLoading).toBe(false);
  });

  it('a response landing after unmount is a no-op (epoch invalidation on cleanup)', async () => {
    const api = makeApi();
    api.getStats.mockResolvedValue({ success: false });
    const a = deferred<unknown>();
    api.getPendingPayments.mockReturnValueOnce(a.promise);
    api.getPayments.mockResolvedValue({ success: true, data: [], pagination: emptyPagination });

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = renderWorklist(api);

    unmount();

    await act(async () => { a.resolve(okPending([1])); });
    await act(async () => { await Promise.resolve(); });

    expect(errorSpy).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});
