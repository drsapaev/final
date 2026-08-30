/**
 * PR-UI-14-1 unit contract: useCashierWorklistData — the cashier data
 * lifecycle slice (fetch effects + pagination + refresh lifecycle) moved
 * verbatim from CashierPanel.
 *
 * Pins the externally observable load semantics that previously lived inline
 * in CashierPanel effects:
 *  - stats load: success sets snapshot; failure resets to empty snapshot
 *  - pending load: success maps data + pagination; failure clears rows
 *  - history load: success maps data + pagination (or falls back to
 *    totalPages=1 / totalItems=data.length); failure clears rows
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

  it('stats failure resets snapshot to empty; pending/history failures clear rows', async () => {
    const api = makeApi();
    api.getStats.mockRejectedValue(new Error('boom'));
    api.getPendingPayments.mockResolvedValue({ success: false, data: [], error: 'backend', pagination: { total: 0, page: 1, size: 20, pages: 1 } });
    api.getPayments.mockRejectedValue(new Error('boom'));

    const { result } = renderWorklist(api);

    await waitFor(() => {
      expect(result.current.stats).toEqual({
        total_amount: 0, cash_amount: 0, card_amount: 0,
        pending_count: 0, pending_amount: 0, paid_count: 0, cancelled_count: 0,
      });
    });
    await waitFor(() => {
      expect(result.current.appointments).toEqual([]);
      expect(result.current.payments).toEqual([]);
      expect(result.current.historyLoading).toBe(false);
    });
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
