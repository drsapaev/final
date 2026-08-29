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
 */
import { describe, expect, it } from 'vitest';

import {
  initialWorklistDataState,
  worklistDataReducer,
  type WorklistDataState,
} from '../useRegistrarWorklistData';

const withState = (patch: Partial<WorklistDataState>): WorklistDataState => ({
  ...initialWorklistDataState,
  ...patch,
});

const rows = [{ id: 1 }, { id: 2 }] as unknown as WorklistDataState['appointments'];

describe('worklistDataReducer (PR-UI-13-1)', () => {
  it('initial state: empty appointments, dataSource loading, not loading, zeroed pagination', () => {
    expect(initialWorklistDataState).toEqual({
      appointments: [],
      dataSource: 'loading',
      appointmentsLoading: false,
      paginationInfo: { total: 0, hasMore: false, loadingMore: false },
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
      });
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
  });

  describe('LOAD_FAILED', () => {
    it('non-silent: dataSource=error with empty appointments', () => {
      const state = withState({ appointments: rows, dataSource: 'loading' });
      const next = worklistDataReducer(state, { type: 'LOAD_FAILED', silent: false });
      expect(next.dataSource).toBe('error');
      expect(next.appointments).toEqual([]);
    });

    it('silent: keeps dataSource, clears appointments', () => {
      const state = withState({ appointments: rows, dataSource: 'api' });
      const next = worklistDataReducer(state, { type: 'LOAD_FAILED', silent: true });
      expect(next.dataSource).toBe('api');
      expect(next.appointments).toEqual([]);
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
});
