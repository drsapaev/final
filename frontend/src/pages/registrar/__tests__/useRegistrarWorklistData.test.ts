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

/**
 * REG-FE-034 (registrar audit ledger 3803): malformed HTTP 200 envelopes
 * must fail closed. A 200 body without a queues array (contract regression,
 * proxy, bad deploy) is a LOAD FAILURE — not a valid empty clinical day.
 * The valid empty day remains { queues: [] }.
 */
describe('useRegistrarWorklistData — REG-FE-034 malformed 200 envelopes fail closed', () => {
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

  it.each([
    { queues: null },
    { message: 'temporary issue' },
    { other: [] },
  ])('a primary 200 body %j is a load error, not a valid empty queue', async (body) => {
    vi.mocked(api.get).mockImplementation(() => Promise.resolve({ data: body }) as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.dataSource).toBe('error');
    expect(result.current.appointments).toEqual([]);
  });

  it('{ queues: [] } remains a valid authoritative empty day', async () => {
    vi.mocked(api.get).mockImplementation(() => Promise.resolve({ data: { queues: [] } }) as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.dataSource).toBe('api');
    expect(result.current.appointments).toEqual([]);
    expect(result.current.stale).toBe(false);
  });

  it('a malformed 200 during a refresh keeps the loaded rows and marks them stale', async () => {
    const loaded = [{ id: 'row-1' }];
    const callQueue = [
      Promise.resolve({ data: { queues: [{ entries: loaded }] } }),
      Promise.resolve({ data: { queues: null } }),
    ];
    vi.mocked(api.get).mockImplementation(() => callQueue.shift() as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['row-1']);

    await act(async () => {
      result.current.loadAppointments({ silent: false, source: 'reg_fe_034_refresh' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    // Rows survive the contract failure with an explicit stale flag.
    expect(result.current.appointments.map((a) => a.id)).toEqual(['row-1']);
    expect(result.current.stale).toBe(true);
    expect(result.current.dataSource).toBe('api');
  });

  // REG-FE-067: the per-queue contract validation. The old
  // `Array.isArray(queue.entries) ? queue.entries : []` coerced a broken
  // queue element into "no entries" — a single malformed queue rendered as
  // a valid EMPTY day (LOAD_EMPTY) or silently dropped that queue's rows
  // while the healthy queues still rendered.
  it.each([
    { queues: [{ entries: null }] },
    { queues: [{ entries: 'not-an-array' }] },
    { queues: [{ entries: { 0: 'object-not-array' } }] },
    { queues: [42] },
  ])('a primary 200 body with a malformed queue element %j is a load error, not a valid empty queue (REG-FE-067)', async (body) => {
    vi.mocked(api.get).mockImplementation(() => Promise.resolve({ data: body }) as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.dataSource).toBe('error');
    expect(result.current.appointments).toEqual([]);
  });

  it('a queue element without entries but valid entries elsewhere must not silently drop patients (REG-FE-067)', async () => {
    // One healthy queue with a real row + one broken queue (entries: null):
    // the old code rendered ONLY the healthy queue's row and pretended the
    // broken queue had no patients — silent partial data loss.
    const body = {
      queues: [
        { entries: [{ id: 'row-1' }] },
        { entries: null },
      ],
    };
    vi.mocked(api.get).mockImplementation(() => Promise.resolve({ data: body }) as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.dataSource).toBe('error');
    expect(result.current.appointments).toEqual([]);
  });

  it('a queue with an empty entries array remains a valid empty queue (REG-FE-067)', async () => {
    vi.mocked(api.get).mockImplementation(() => Promise.resolve({ data: { queues: [{ entries: [] }] } }) as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.dataSource).toBe('api');
    expect(result.current.appointments).toEqual([]);
    expect(result.current.stale).toBe(false);
  });

  it('a malformed queue element during a refresh keeps the loaded rows and marks them stale (REG-FE-067)', async () => {
    const loaded = [{ id: 'row-1' }];
    const callQueue = [
      Promise.resolve({ data: { queues: [{ entries: loaded }] } }),
      Promise.resolve({ data: { queues: [{ entries: null }] } }),
    ];
    vi.mocked(api.get).mockImplementation(() => callQueue.shift() as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['row-1']);

    await act(async () => {
      result.current.loadAppointments({ silent: false, source: 'reg_fe_067_refresh' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['row-1']);
    expect(result.current.stale).toBe(true);
    expect(result.current.dataSource).toBe('api');
  });
});

/**
 * REG-FE-007 / REG-FE-020 / REG-FE-021 (registrar audit ledger 3803) —
 * worklist refresh lifecycle.
 *
 * 007: HTTP 429 must surface as an explicit load failure (error on the
 *      primary fetch, kept rows + stale on a refresh) — the 60s auto-refresh
 *      cooldown alone is not user-visible state.
 * 020: the shared in-flight guard and the 429 cooldown belong to the
 *      AUTHORITATIVE request: a superseded request settling early must not
 *      release the guard for a newer pending load (letting an unnecessary
 *      auto-refresh C claim the newest sequence id), and a superseded 429
 *      must not freeze auto-refresh after the newer request succeeded.
 * 021: the auto-refresh interval reads the any-dialog flag on EVERY tick,
 *      so opening a dialog pauses refresh and closing it resumes — without
 *      waiting for an effect re-run; an interval created while a dialog was
 *      open still recovers after it closes.
 */
describe('useRegistrarWorklistData — refresh lifecycle (REG-FE-007/020/021)', () => {
  const hookDeps = (anyDialogOpenRef: { current: boolean } = { current: false }) => ({
    searchParams: new URLSearchParams(),
    activeTab: null,
    showCalendar: false,
    historyDate: '',
    showWizard: false,
    anyDialogOpenRef,
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

  const rateLimited = () => Promise.reject({ response: { status: 429 } });

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('REG-FE-007: a non-silent 429 primary load surfaces an explicit error state, not a silent spinner', async () => {
    vi.mocked(api.get).mockImplementation(() => rateLimited() as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.dataSource).toBe('error');
    expect(result.current.appointmentsLoading).toBe(false);
  });

  it('REG-FE-007: a 429 during a refresh keeps the loaded rows and marks them stale', async () => {
    // Lazy factories: a rejected promise created before its consumer attaches
    // a handler would surface as an unhandled rejection between act blocks.
    const callQueue = [
      () => Promise.resolve({ data: { queues: [{ entries: [{ id: 'row-1' }] }] } }),
      () => rateLimited(),
    ];
    vi.mocked(api.get).mockImplementation(() => callQueue.shift()!() as never);
    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['row-1']);

    await act(async () => {
      result.current.loadAppointments({ silent: false, source: 'reg_fe_007_refresh' });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['row-1']);
    expect(result.current.stale).toBe(true);
    expect(result.current.dataSource).toBe('api');
  });

  it('REG-FE-020: a superseded request settling early keeps the in-flight guard for the newer pending load', async () => {
    const lateA = deferred<{ data: { queues: unknown[] } }>();
    const freshB = deferred<{ data: { queues: unknown[] } }>();
    const callQueue: Array<Promise<{ data: { queues: unknown[] } }>> = [
      Promise.resolve({ data: { queues: [] } }),
      lateA.promise,
      freshB.promise,
    ];
    vi.mocked(api.get).mockImplementation(() => callQueue.shift() as never);

    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const baselineCalls = vi.mocked(api.get).mock.calls.length;

    // A (old date) starts and hangs; B (new date) starts and stays pending.
    let aPromise: Promise<unknown> | null = null;
    await act(async () => {
      aPromise = result.current.loadAppointments({ silent: false, source: 'race_a' });
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      void result.current.loadAppointments({ silent: false, source: 'race_b' });
      await vi.advanceTimersByTimeAsync(0);
    });

    // A settles while B is still pending: the shared in-flight guard must
    // stay held by B, so the next auto-refresh tick must NOT start request C.
    await act(async () => {
      lateA.resolve({ data: { queues: [{ entries: [{ id: 'old-row' }] }] } });
      await aPromise;
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      result.current.loadAppointments({ silent: true, source: 'auto_refresh' });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(vi.mocked(api.get).mock.calls.length).toBe(baselineCalls + 2); // A and B only — no C

    // B resolves and releases the guard: a later auto-refresh may run again.
    await act(async () => {
      freshB.resolve({ data: { queues: [{ entries: [{ id: 'new-row' }] }] } });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['new-row']);
    await act(async () => {
      result.current.loadAppointments({ silent: true, source: 'auto_refresh' });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(vi.mocked(api.get).mock.calls.length).toBe(baselineCalls + 3);
  });

  it('REG-FE-020: a superseded 429 does not freeze auto-refresh after the newer request succeeds', async () => {
    const lateA = deferred<{ data: { queues: unknown[] } }>();
    const freshB = deferred<{ data: { queues: unknown[] } }>();
    const callQueue: Array<Promise<{ data: { queues: unknown[] } }>> = [
      Promise.resolve({ data: { queues: [] } }),
      lateA.promise,
      freshB.promise,
      Promise.resolve({ data: { queues: [{ entries: [{ id: 'post-cooldown-row' }] }] } }),
    ];
    vi.mocked(api.get).mockImplementation(() => callQueue.shift() as never);

    const { result } = renderHook(() => useRegistrarWorklistData(hookDeps()));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    let aPromise: Promise<unknown> | null = null;
    await act(async () => {
      aPromise = result.current.loadAppointments({ silent: false, source: 'race_a_429' });
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      void result.current.loadAppointments({ silent: false, source: 'race_b_ok' });
      await vi.advanceTimersByTimeAsync(0);
    });

    // A (superseded) rejects with 429: must NOT install the 60s cooldown.
    await act(async () => {
      lateA.reject({ response: { status: 429 } });
      await aPromise!.then(() => undefined, () => undefined);
      await vi.advanceTimersByTimeAsync(0);
    });
    // B succeeds.
    await act(async () => {
      freshB.resolve({ data: { queues: [{ entries: [{ id: 'b-row' }] }] } });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['b-row']);

    // An auto-refresh right after must NOT be blocked by A's stale cooldown.
    await act(async () => {
      result.current.loadAppointments({ silent: true, source: 'auto_refresh' });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.appointments.map((a) => a.id)).toEqual(['post-cooldown-row']);
  });

  it('REG-FE-021: opening a dialog pauses the interval refresh and closing it resumes', async () => {
    const anyDialogOpenRef = { current: false };
    vi.mocked(api.get).mockImplementation(() => Promise.resolve({ data: { queues: [] } }) as never);
    renderHook(() => useRegistrarWorklistData(hookDeps(anyDialogOpenRef)));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const baselineCalls = vi.mocked(api.get).mock.calls.length;

    // A payment/cancel dialog opens — no effect re-run, only the ref flips.
    anyDialogOpenRef.current = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(61_000);
    });
    expect(vi.mocked(api.get).mock.calls.length).toBe(baselineCalls); // paused

    // The dialog closes: the next ticks refresh again.
    anyDialogOpenRef.current = false;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(61_000);
    });
    expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThan(baselineCalls); // resumed
  });

  it('REG-FE-021: an interval created while a dialog was open still refreshes after it closes', async () => {
    const anyDialogOpenRef = { current: true };
    vi.mocked(api.get).mockImplementation(() => Promise.resolve({ data: { queues: [] } }) as never);
    renderHook(() => useRegistrarWorklistData(hookDeps(anyDialogOpenRef)));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const baselineCalls = vi.mocked(api.get).mock.calls.length;

    // The dialog closes without any effect re-run (ref flip only).
    anyDialogOpenRef.current = false;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(61_000);
    });
    expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThan(baselineCalls);
  });
});
