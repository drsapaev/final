/**
 * PR-UI-13-1 unit contract: worklistDataReducer — the worklist data
 * state machine (plan §PR-UI-13 "top-level state machine").
 *
 * Each action maps 1:1 to the original setState sequence from
 * RegistrarPanel.loadAppointments. These tests pin the transition table,
 * including the intentional silent-mode semantics (silent loads keep the
 * indicators untouched) and the legacy quirk where a non-silent load that
 * hits 429 leaves dataSource at 'loading' with loading=false (original
 * behavior preserved verbatim).
 *
 * RQ-22 (F-18): the failed-refresh semantics are re-contracted — a refresh
 * failure keeps previously loaded rows (marked stale) instead of wiping
 * them into a misleading "successfully empty" list, and a late response of
 * a superseded request (e.g. a previous calendar date) must not overwrite
 * a newer sample (S-19).
 */
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'synthetic-test-token') },
}));
vi.mock('../../../services/notify', () => ({ default: { error: vi.fn(), success: vi.fn() } }));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { api } from '../../../api/client';
import {
  initialWorklistDataState,
  useRegistrarWorklistData,
  worklistDataReducer,
  type WorklistDataState,
} from '../useRegistrarWorklistData';

const withState = (patch: Partial<WorklistDataState>): WorklistDataState => ({
  ...initialWorklistDataState,
  ...patch,
});

const rows = [{ id: 1 }, { id: 2 }] as unknown as WorklistDataState['appointments'];

describe('worklistDataReducer (PR-UI-13-1)', () => {
  it('initial state: empty appointments, dataSource loading, not loading, zeroed pagination, not stale', () => {
    expect(initialWorklistDataState).toEqual({
      appointments: [],
      dataSource: 'loading',
      appointmentsLoading: false,
      paginationInfo: { total: 0, hasMore: false, loadingMore: false },
      stale: false,
    });
  });

  describe('LOAD_STARTED', () => {
    it('non-silent sets loading=true and dataSource=loading', () => {
      const state = withState({ appointments: rows, dataSource: 'api', appointmentsLoading: false });
      const next = worklistDataReducer(state, { type: 'LOAD_STARTED', silent: false });
      expect(next.appointmentsLoading).toBe(true);
      expect(next.dataSource).toBe('loading');
      expect(next.appointments).toBe(rows); // rows untouched at start
    });

    it('silent load is a no-op (indicators untouched)', () => {
      const state = withState({ dataSource: 'api', appointmentsLoading: false });
      expect(worklistDataReducer(state, { type: 'LOAD_STARTED', silent: true })).toBe(state);
    });
  });

  describe('LOAD_TOKEN_MISSING', () => {
    it('non-silent: dataSource=api with empty appointments', () => {
      const state = withState({ appointments: rows, dataSource: 'loading', appointmentsLoading: true });
      const next = worklistDataReducer(state, { type: 'LOAD_TOKEN_MISSING', silent: false });
      expect(next.dataSource).toBe('api');
      expect(next.appointments).toEqual([]);
    });

    it('silent: keeps dataSource, clears appointments', () => {
      const state = withState({ appointments: rows, dataSource: 'api' });
      const next = worklistDataReducer(state, { type: 'LOAD_TOKEN_MISSING', silent: true });
      expect(next.dataSource).toBe('api');
      expect(next.appointments).toEqual([]);
    });
  });

  describe('LOAD_EMPTY', () => {
    it('clears appointments, sets api, forces loading=false (original quirk: unconditional)', () => {
      const state = withState({ appointments: rows, dataSource: 'loading', appointmentsLoading: true });
      const next = worklistDataReducer(state, { type: 'LOAD_EMPTY' });
      expect(next).toEqual({
        appointments: [],
        dataSource: 'api',
        appointmentsLoading: false,
        paginationInfo: state.paginationInfo,
        stale: false,
      });
    });

    it('RQ-22: a successful EMPTY response clears a previously set stale flag', () => {
      const state = withState({ stale: true });
      const next = worklistDataReducer(state, { type: 'LOAD_EMPTY' });
      expect(next.stale).toBe(false);
    });
  });

  describe('LOAD_SUCCEEDED', () => {
    it('sets rows and dataSource=api', () => {
      const state = withState({ appointments: [], dataSource: 'loading', appointmentsLoading: true });
      const next = worklistDataReducer(state, { type: 'LOAD_SUCCEEDED', rows });
      expect(next.appointments).toBe(rows);
      expect(next.dataSource).toBe('api');
      // NOTE: loading is cleared by LOAD_FINALLY, not here — mirrors original.
      expect(next.appointmentsLoading).toBe(true);
    });

    it('RQ-22: a successful response clears the stale flag', () => {
      const state = withState({ stale: true, appointments: rows, dataSource: 'api' });
      const next = worklistDataReducer(state, { type: 'LOAD_SUCCEEDED', rows: [] });
      expect(next.stale).toBe(false);
    });
  });

  describe('LOAD_FAILED', () => {
    // RQ-22 / F-18: a failed refresh must NOT wipe previously loaded rows
    // into a misleading "successfully empty" list — rows stay on screen
    // with an explicit staleness flag and a retry affordance.
    it('RQ-22 non-silent refresh failure with rows: rows are kept and marked stale', () => {
      const state = withState({ appointments: rows, dataSource: 'api', appointmentsLoading: true });
      const next = worklistDataReducer(state, { type: 'LOAD_FAILED', silent: false });
      expect(next.appointments).toBe(rows);
      expect(next.stale).toBe(true);
      // Rows remain visible → the state is not the plain primary error.
      expect(next.dataSource).toBe('api');
    });

    it('RQ-22 silent (auto-refresh) failure with rows: rows are kept, indicators untouched, stale set', () => {
      const state = withState({ appointments: rows, dataSource: 'api', appointmentsLoading: false });
      const next = worklistDataReducer(state, { type: 'LOAD_FAILED', silent: true });
      expect(next.appointments).toBe(rows);
      expect(next.stale).toBe(true);
      expect(next.dataSource).toBe('api');
      expect(next.appointmentsLoading).toBe(false);
    });

    it('primary failure (nothing loaded yet): plain error state with empty list — distinct from an empty answer', () => {
      const state = withState({ appointments: [], dataSource: 'loading', appointmentsLoading: true });
      const next = worklistDataReducer(state, { type: 'LOAD_FAILED', silent: false });
      expect(next.dataSource).toBe('error');
      expect(next.appointments).toEqual([]);
      expect(next.stale).toBe(false);
    });

    it('stale flag does not double-apply on a repeated failure', () => {
      const state = withState({ appointments: rows, dataSource: 'api', stale: true });
      const next = worklistDataReducer(state, { type: 'LOAD_FAILED', silent: true });
      expect(next.stale).toBe(true);
      expect(next.appointments).toBe(rows);
    });
  });

  describe('LOAD_FINALLY', () => {
    it('non-silent clears the loading flag', () => {
      const state = withState({ appointmentsLoading: true });
      expect(worklistDataReducer(state, { type: 'LOAD_FINALLY', silent: false }).appointmentsLoading).toBe(false);
    });

    it('silent is a no-op', () => {
      const state = withState({ appointmentsLoading: true });
      expect(worklistDataReducer(state, { type: 'LOAD_FINALLY', silent: true })).toBe(state);
    });
  });

  describe('PAGINATION_REPLACED / PAGINATION_PATCH', () => {
    it('REPLACED sets the whole pagination object (load path: total=count, hasMore=false)', () => {
      const next = worklistDataReducer(initialWorklistDataState, {
        type: 'PAGINATION_REPLACED',
        pagination: { total: 7, hasMore: false, loadingMore: false },
      });
      expect(next.paginationInfo).toEqual({ total: 7, hasMore: false, loadingMore: false });
    });

    it('PATCH merges partial updates (load-more in-flight flags)', () => {
      const state = withState({ paginationInfo: { total: 10, hasMore: true, loadingMore: false } });
      const loading = worklistDataReducer(state, { type: 'PAGINATION_PATCH', patch: { loadingMore: true } });
      expect(loading.paginationInfo).toEqual({ total: 10, hasMore: true, loadingMore: true });
      const done = worklistDataReducer(loading, { type: 'PAGINATION_PATCH', patch: { loadingMore: false } });
      expect(done.paginationInfo).toEqual({ total: 10, hasMore: true, loadingMore: false });
    });
  });

  describe('APPOINTMENTS_UPDATER', () => {
    it('applies a functional update (setAppointments shim for useRegistrarReschedule)', () => {
      const state = withState({ appointments: rows });
      const next = worklistDataReducer(state, {
        type: 'APPOINTMENTS_UPDATER',
        // AppointmentId is a branded string type — compare via String() to stay type-safe.
        updater: (prev) => prev.filter((a) => String(a.id) !== '1'),
      });
      expect(next.appointments).toEqual([{ id: 2 }]);
    });
  });

  it('transition chain reproduces the legacy non-silent 429 quirk (dataSource stays loading)', () => {
    // Original: non-silent call → setAppointmentsLoading(true) + setDataSource('loading')
    // → 429 → return (no state change) → finally: setAppointmentsLoading(false).
    // Net: dataSource='loading', loading=false.
    let state = initialWorklistDataState;
    state = worklistDataReducer(state, { type: 'LOAD_STARTED', silent: false });
    state = worklistDataReducer(state, { type: 'LOAD_FINALLY', silent: false });
    expect(state.dataSource).toBe('loading');
    expect(state.appointmentsLoading).toBe(false);
  });

  it('full happy-path chain: started → succeeded → finally', () => {
    let state = worklistDataReducer(initialWorklistDataState, { type: 'LOAD_STARTED', silent: false });
    state = worklistDataReducer(state, {
      type: 'PAGINATION_REPLACED',
      pagination: { total: 2, hasMore: false, loadingMore: false },
    });
    state = worklistDataReducer(state, { type: 'LOAD_SUCCEEDED', rows });
    state = worklistDataReducer(state, { type: 'LOAD_FINALLY', silent: false });
    expect(state).toEqual({
      appointments: rows,
      dataSource: 'api',
      appointmentsLoading: false,
      paginationInfo: { total: 2, hasMore: false, loadingMore: false },
      stale: false,
    });
  });

  it('full silent-refresh chain: no indicator churn', () => {
    const settled = withState({ appointments: rows, dataSource: 'api', appointmentsLoading: false });
    let state = settled;
    state = worklistDataReducer(state, { type: 'LOAD_STARTED', silent: true });
    state = worklistDataReducer(state, { type: 'LOAD_SUCCEEDED', rows });
    state = worklistDataReducer(state, { type: 'LOAD_FINALLY', silent: true });
    expect(state.appointments).toBe(rows);
    expect(state.dataSource).toBe('api');
    expect(state.appointmentsLoading).toBe(false);
  });

  it('RQ-22 full failed-then-recovered chain: rows survive the failure and stale clears on success', () => {
    let state = withState({ appointments: rows, dataSource: 'api', appointmentsLoading: false });
    // A non-silent refresh starts (calendar/manual retry): loading indicators on, rows untouched.
    state = worklistDataReducer(state, { type: 'LOAD_STARTED', silent: false });
    expect(state.appointments).toBe(rows);
    // The refresh fails: rows are KEPT and marked stale (F-18 fixed).
    state = worklistDataReducer(state, { type: 'LOAD_FAILED', silent: false });
    expect(state.appointments).toBe(rows);
    expect(state.stale).toBe(true);
    state = worklistDataReducer(state, { type: 'LOAD_FINALLY', silent: false });
    // A later retry succeeds: fresh rows replace the stale ones, flag clears.
    const fresh = [{ id: 3 }] as unknown as WorklistDataState['appointments'];
    state = worklistDataReducer(state, { type: 'LOAD_SUCCEEDED', rows: fresh });
    state = worklistDataReducer(state, { type: 'LOAD_FINALLY', silent: false });
    expect(state.appointments).toBe(fresh);
    expect(state.stale).toBe(false);
    expect(state.dataSource).toBe('api');
  });
});

/**
 * RQ-22 / S-19: late-response race. When a new load starts before the
 * previous one resolves (calendar date switch, manual retry after timeout),
 * the LATE response of the superseded request must not overwrite the newer
 * sample. Without a request-sequence guard the stale response wins and the
 * worklist silently shows rows for the wrong date.
 */
describe('useRegistrarWorklistData — RQ-22 late-response race guard (S-19)', () => {
  const hookDeps = () => ({
    searchParams: new URLSearchParams(),
    activeTab: null,
    showCalendar: false,
    historyDate: '',
    showWizard: false,
    anyDialogOpenRef: { current: false },
    enrichAppointmentsWithPatientData: async (rows: Record<string, unknown>[]) => rows,
    loadIntegratedData: () => undefined,
    tI18n: (key: string) => key,
  });

  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
  };

  it('a late response of the superseded request does not overwrite the newer sample', async () => {
    const lateRows = [{ id: 'late-old-date' }];
    const freshRows = [{ id: 'fresh-new-date' }];
    const late = deferred<{ data: { queues: unknown[] } }>();
    const fresh = deferred<{ data: { queues: unknown[] } }>();

    // Call order: (0) hook initial-load, (1) request A, (2) request B.
    const callQueue = [
      Promise.resolve({ data: { queues: [] } }),
      late.promise,
      fresh.promise,
    ];
    vi.mocked(api.get).mockImplementation(() => callQueue.shift() as Promise<{ data: { queues: unknown[] } }>);

    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));

    // Request A (e.g. previous calendar date) starts and hangs.
    await act(async () => {
      result.current.loadAppointments({ silent: false, source: 'race_a' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // Request B (new date) starts and resolves first.
    await act(async () => {
      result.current.loadAppointments({ silent: false, source: 'race_b' });
      fresh.resolve({ data: { queues: [{ entries: freshRows }] } } as never);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['fresh-new-date']);

    // Request A finally answers LATE: it must be ignored as a stale response.
    await act(async () => {
      late.resolve({ data: { queues: [{ entries: lateRows }] } } as never);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(result.current.appointments.map((a) => a.id)).toEqual(['fresh-new-date']);
    expect(result.current.dataSource).toBe('api');
    expect(result.current.stale).toBe(false);
    expect(result.current.paginationInfo.total).toBe(freshRows.length);
  });

  it('a late FAILURE of the superseded request does not clobber the newer sample', async () => {
    const freshRows = [{ id: 'fresh-only' }];
    const late = deferred<{ data: { queues: unknown[] } }>();
    const fresh = deferred<{ data: { queues: unknown[] } }>();

    // Call order: (0) hook initial-load, (1) request A, (2) request B.
    const callQueue = [
      Promise.resolve({ data: { queues: [] } }),
      late.promise,
      fresh.promise,
    ];
    vi.mocked(api.get).mockImplementation(() => callQueue.shift() as Promise<{ data: { queues: unknown[] } }>);

    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));

    await act(async () => {
      result.current.loadAppointments({ silent: false, source: 'race_a_fail' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    await act(async () => {
      result.current.loadAppointments({ silent: false, source: 'race_b_ok' });
      fresh.resolve({ data: { queues: [{ entries: freshRows }] } } as never);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['fresh-only']);

    // The superseded request fails late: no stale wipe, no flag change.
    await act(async () => {
      late.reject(new Error('late network failure'));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(result.current.appointments.map((a) => a.id)).toEqual(['fresh-only']);
    expect(result.current.stale).toBe(false);
    expect(result.current.dataSource).toBe('api');
  });
});
