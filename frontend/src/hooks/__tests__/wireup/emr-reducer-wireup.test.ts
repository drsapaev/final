/**
 * Wire-up integration tests — verify invariants + state machines are
 * actually called in hooks/reducers.
 *
 * These are NOT unit tests of the invariants themselves (those exist in
 * types/domain/invariants/__tests__/). These tests verify that the hooks
 * and reducers CALL the invariant validators at the right points.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { emrReducer, EMR_ACTIONS, initialState } from '../../../reducers/emrReducer';
import type { EmrState } from '../../../types/features/emr';

describe('EMR reducer wire-up — state machine transitions', () => {
  it('SAVE_START transitions idle → saving', () => {
    const state: EmrState = { ...initialState, status: 'idle' };
    const next = emrReducer(state, { type: EMR_ACTIONS.SAVE_START, payload: {} });
    expect(next.status).toBe('saving');
  });

  it('SAVE_SUCCESS transitions saving → idle', () => {
    const state: EmrState = { ...initialState, status: 'saving' };
    const next = emrReducer(state, {
      type: EMR_ACTIONS.SAVE_SUCCESS,
      payload: { emr: { data: {}, version: 1 } },
    });
    expect(next.status).toBe('idle');
  });

  it('SAVE_ERROR transitions saving → error', () => {
    const state: EmrState = { ...initialState, status: 'saving' };
    const next = emrReducer(state, {
      type: EMR_ACTIONS.SAVE_ERROR,
      payload: { error: 'Network error' },
    });
    expect(next.status).toBe('error');
  });

  it('CONFLICT_DETECTED transitions saving → conflict', () => {
    const state: EmrState = { ...initialState, status: 'saving' };
    const next = emrReducer(state, {
      type: EMR_ACTIONS.CONFLICT_DETECTED,
      payload: {
        current_version: { data: 'server' },
        your_version: { data: 'client' },
        last_edited_by: 'other_user',
        last_edited_at: '2024-01-01T00:00:00Z',
      },
    });
    expect(next.status).toBe('conflict');
  });

  it('CONFLICT_RESOLVED transitions conflict → idle', () => {
    const state: EmrState = { ...initialState, status: 'conflict' };
    const next = emrReducer(state, {
      type: EMR_ACTIONS.CONFLICT_RESOLVED,
      payload: { data: { resolved: true }, rowVersion: 2 },
    });
    expect(next.status).toBe('idle');
  });

  it('forbidden transition (idle → error) is no-op', () => {
    // SAVE_ERROR from idle is forbidden — state machine should block it
    const state: EmrState = { ...initialState, status: 'idle' };
    const next = emrReducer(state, {
      type: EMR_ACTIONS.SAVE_ERROR,
      payload: { error: 'should not happen' },
    });
    // applyEmrTransition returns original state on forbidden transition
    expect(next.status).toBe('idle');
  });

  it('forbidden transition (idle → conflict) is no-op', () => {
    const state: EmrState = { ...initialState, status: 'idle' };
    const next = emrReducer(state, {
      type: EMR_ACTIONS.CONFLICT_DETECTED,
      payload: {
        current_version: {},
        your_version: {},
        last_edited_by: '',
        last_edited_at: '',
      },
    });
    expect(next.status).toBe('idle');
  });

  it('LOAD resets to idle regardless of current status', () => {
    const state: EmrState = { ...initialState, status: 'error' };
    const next = emrReducer(state, {
      type: EMR_ACTIONS.LOAD,
      payload: { emr: { data: { loaded: true }, version: 1 } },
    });
    expect(next.status).toBe('idle');
  });
});
