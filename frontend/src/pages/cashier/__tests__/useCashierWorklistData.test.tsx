/**
 * PR-UI-14-1 unit contract: useCashierWorklistData — the cashier worklist
 * data-lifecycle hook extracted verbatim from CashierPanel.tsx.
 *
 * Pins the observable contracts:
 * - initial state (empty lists, zeroed stats/pagination, single-date mode,
 *   loading indicators already on — the mount effects run synchronously
 *   up to their first await)
 * - the three load effects and their exact request payloads (page/size/date
 *   params, search passthrough, status filter mapping 'all' → undefined)
 * - pagination wiring (server pagination absent → totalPages=1, totalItems=len)
 * - failure paths keep lists empty (success:false and thrown errors)
 * - page-reset effect: date change resets BOTH pages
 * - refresh lifecycle: bumpRefreshKey refreshes WITHOUT resetting currentPage
 *   (processPayment call shape) while triggerDataReload resets BOTH pages
 *   (the distinction is unit-pinned because the original code reset only
 *   pendingPage after a payment — porting must not "simplify" this)
 * - payments SSOT API re-export (stable identity pass-through)
 * - URL patientId deep-link: query initializer reads window.location.search,
 *   the effect reads the router location and resolves the patient name
 *
 * Determinism pattern: tests asserting pre-load state use never-resolving
 * mocks (no state updates can race); tests asserting post-load state wait
 * for the FINAL settled state (both loading flags false) before asserting.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const getStats = vi.hoisted(() => vi.fn());
const getPendingPayments = vi.hoisted(() => vi.fn());
const getPayments = vi.hoisted(() => vi.fn());
const createPayment = vi.hoisted(() => vi.fn());
const refundPayment = vi.hoisted(() => vi.fn());

// Stable function identities across renders — the REAL usePayments wraps its
// callbacks in useCallback([]); the mock must preserve that invariant or the
// extracted effects (which keep the original deps arrays) would re-run on
// every re-render, exactly like they would against a broken real hook.
vi.mock('../../../hooks/usePayments', () => ({
  usePayments: () => ({
    getStats,
    getPendingPayments,
    getPayments,
    createPayment,
    refundPayment,
  }),
}));

// Debounce is not under test here — identity keeps effect deps synchronous.
vi.mock('../../../hooks/useDebouncedCallback', () => ({
  useDebouncedCallback: (fn: unknown) => fn,
  useDebouncedValue: (value: unknown) => value,
}));

const getPatient = vi.hoisted(() => vi.fn());
vi.mock('../../../api/patients', () => ({
  getPatient: (...a: unknown[]) => getPatient(...a),
}));

// vi.hoisted: api/client.ts reads the token at module-load time, so the mock
// factory must not depend on a later-initialized const.
const { getAccessToken } = vi.hoisted(() => ({ getAccessToken: vi.fn() }));
vi.mock('../../../utils/tokenManager', () => {
  const tokenManager = { getAccessToken: () => getAccessToken() };
  return { default: tokenManager, tokenManager };
});

import { useCashierWorklistData } from '../useCashierWorklistData';

const today = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const renderDataHook = (initialPath = '/cashier') =>
  renderHook(() => useCashierWorklistData(), {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
    ),
  }).result;

// Never-resolving stubs freeze the load lifecycle at its synchronous pre-await
// state — nothing can resolve and mutate state mid-assertion.
const freezeLoads = () => {
  getStats.mockReturnValue(new Promise(() => {}));
  getPendingPayments.mockReturnValue(new Promise(() => {}));
  getPayments.mockReturnValue(new Promise(() => {}));
};

// Wait until BOTH loading flags settle false — the final post-load state.
const settleLoads = (res: { current: ReturnType<typeof useCashierWorklistData> }) =>
  waitFor(() => {
    expect(res.current.pendingLoading).toBe(false);
    expect(res.current.historyLoading).toBe(false);
  });

beforeEach(() => {
  getStats.mockReset();
  getPendingPayments.mockReset();
  getPayments.mockReset();
  getPatient.mockReset();
  getAccessToken.mockReset();
  getAccessToken.mockReturnValue('token');
  getStats.mockResolvedValue({ success: true, data: { total_amount: 10 } });
  getPendingPayments.mockResolvedValue({ success: true, data: [], pagination: { pages: 1, total: 0 } });
  getPayments.mockResolvedValue({ success: true, data: [], pagination: { pages: 1, total: 0 } });
});

describe('useCashierWorklistData (PR-UI-14-1)', () => {
  it('initial state: empty lists, zeroed stats/pagination, single-date mode, loading on', () => {
    freezeLoads();
    const res = renderDataHook();
    // all three load effects fired (synchronous part)…
    expect(getStats).toHaveBeenCalledTimes(1);
    expect(getPendingPayments).toHaveBeenCalledTimes(1);
    expect(getPayments).toHaveBeenCalledTimes(1);
    // …but nothing has resolved yet: pre-load state is observable
    expect(res.current.query).toBe('');
    expect(res.current.status).toBe('all');
    expect(res.current.dateMode).toBe('single');
    expect(res.current.selectedDate).toBe(today());
    expect(res.current.appointments).toEqual([]);
    expect(res.current.payments).toEqual([]);
    expect(res.current.currentPage).toBe(1);
    expect(res.current.totalPages).toBe(1);
    expect(res.current.totalItems).toBe(0);
    expect(res.current.pendingPage).toBe(1);
    expect(res.current.pendingTotalPages).toBe(1);
    expect(res.current.pendingTotalItems).toBe(0);
    expect(res.current.stats).toEqual({
      total_amount: 0, cash_amount: 0, card_amount: 0,
      pending_count: 0, pending_amount: 0, paid_count: 0, cancelled_count: 0,
    });
    expect(res.current.pendingLoading).toBe(true);
    expect(res.current.historyLoading).toBe(true);
  });

  it('re-exports the payments SSOT API under paymentsHook', () => {
    freezeLoads();
    const res = renderDataHook();
    expect(res.current.paymentsHook.createPayment).toBe(createPayment);
    expect(res.current.paymentsHook.refundPayment).toBe(refundPayment);
  });

  it('loads stats, pending payments and history on mount with canonical params', async () => {
    const res = renderDataHook();
    await settleLoads(res);
    expect(getStats).toHaveBeenCalledWith({ date_from: today(), date_to: today() });
    expect(getPendingPayments).toHaveBeenCalledWith({
      date_from: today(), date_to: today(), search: undefined, page: 1, size: 20,
    });
    expect(getPayments).toHaveBeenCalledWith({
      date_from: today(), date_to: today(), search: undefined, status: undefined, page: 1, size: 20,
    });
    expect(res.current.stats).toEqual({ total_amount: 10 });
  });

  it('maps status filter to the history request (all → undefined)', async () => {
    const res = renderDataHook();
    await settleLoads(res);
    res.current.setStatus('paid');
    await waitFor(() =>
      expect(getPayments).toHaveBeenLastCalledWith({
        date_from: today(), date_to: today(), search: undefined, status: 'paid', page: 1, size: 20,
      }),
    );
  });

  it('wires server pagination for pending and history lists', async () => {
    getPendingPayments.mockResolvedValue({
      success: true,
      data: [{ id: 1 }, { id: 2 }],
      pagination: { pages: 3, total: 41 },
    });
    getPayments.mockResolvedValue({
      success: true,
      data: [{ id: 10 }],
      pagination: { pages: 2, total: 21 },
    });
    const res = renderDataHook();
    await settleLoads(res);
    expect(res.current.appointments).toHaveLength(2);
    expect(res.current.pendingTotalPages).toBe(3);
    expect(res.current.pendingTotalItems).toBe(41);
    expect(res.current.payments).toEqual([{ id: 10 }]);
    expect(res.current.totalPages).toBe(2);
    expect(res.current.totalItems).toBe(21);
  });

  it('history without pagination falls back to a single page sized by data length', async () => {
    getPayments.mockResolvedValue({ success: true, data: [{ id: 1 }, { id: 2 }, { id: 3 }] });
    const res = renderDataHook();
    await settleLoads(res);
    expect(res.current.payments).toHaveLength(3);
    expect(res.current.totalPages).toBe(1);
    expect(res.current.totalItems).toBe(3);
  });

  it('failure paths keep the lists empty (success:false and thrown errors)', async () => {
    getPendingPayments.mockResolvedValue({ success: false, error: 'boom' });
    getPayments.mockRejectedValue(new Error('network'));
    getStats.mockRejectedValue(new Error('down'));
    const res = renderDataHook();
    await settleLoads(res);
    expect(res.current.appointments).toEqual([]);
    expect(res.current.payments).toEqual([]);
    // stats error path resets to the zeroed shape
    expect(res.current.stats).toEqual({
      total_amount: 0, cash_amount: 0, card_amount: 0,
      pending_count: 0, pending_amount: 0, paid_count: 0, cancelled_count: 0,
    });
  });

  it('date change resets BOTH pages', async () => {
    const res = renderDataHook();
    await settleLoads(res);
    res.current.setPendingPage(3);
    await waitFor(() =>
      expect(getPendingPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 3 })),
    );
    res.current.setSelectedDate('2026-01-01');
    await waitFor(() =>
      expect(getPendingPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 })),
    );
    expect(res.current.pendingPage).toBe(1);
    expect(res.current.currentPage).toBe(1);
  });

  it('bumpRefreshKey refreshes WITHOUT resetting currentPage (processPayment shape)', async () => {
    const res = renderDataHook();
    await settleLoads(res);
    res.current.setCurrentPage(2);
    await waitFor(() =>
      expect(getPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })),
    );
    const callsBefore = getPayments.mock.calls.length;
    res.current.bumpRefreshKey();
    await waitFor(() => expect(getPayments.mock.calls.length).toBeGreaterThan(callsBefore));
    // history page must SURVIVE the refresh — original code only reset pendingPage here
    expect(res.current.currentPage).toBe(2);
    expect(getPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }));
  });

  it('triggerDataReload resets BOTH pages and refreshes', async () => {
    const res = renderDataHook();
    await settleLoads(res);
    res.current.setCurrentPage(4);
    res.current.setPendingPage(2);
    await waitFor(() =>
      expect(getPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 4 })),
    );
    res.current.triggerDataReload();
    await waitFor(() => {
      expect(res.current.currentPage).toBe(1);
      expect(res.current.pendingPage).toBe(1);
    });
    expect(getPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 }));
    expect(getPendingPayments).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 }));
  });

  it('URL patientId deep-link resolves the patient name into the search query', async () => {
    // NOTE: the query initializer reads window.location.search (jsdom URL —
    // empty here), while the URL effect reads the ROUTER location. That split
    // is the original behavior and is pinned by this test.
    getPatient.mockResolvedValue({ id: 5, first_name: 'Ivan', last_name: 'Petrov' });
    const res = renderDataHook('/cashier?patientId=5');
    await waitFor(() => expect(getPatient).toHaveBeenCalledWith(5));
    await waitFor(() => expect(res.current.query).toBe('Petrov Ivan'));
  });

  it('URL patientId effect skips the lookup when the token is missing', async () => {
    getAccessToken.mockReturnValue(null);
    const res = renderDataHook('/cashier?patientId=5');
    // absorb the load lifecycle inside an act-wrapped waitFor…
    await settleLoads(res);
    // …getPatient must never have fired without a token
    expect(getPatient).not.toHaveBeenCalled();
    expect(res.current.query).toBe('');
  });
});
