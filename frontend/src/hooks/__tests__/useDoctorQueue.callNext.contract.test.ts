/**
 * QAPI-FE-001 (audit 3886, additional consumer per the ledger): the
 * useDoctorQueue helper implements the SAME null/absent
 * `next_call_entry_id` fallback already fixed in services/queue.ts —
 * `selectNextCallEntryId` re-derives a caller via the first can_call entry
 * when the canonical backend field is null or missing. The backend
 * `_queue_ops` always returns the field (explicit null = «none callable»).
 *
 * Red-first: on pre-fix source cases 1 and 2 fail (the guessed entry is
 * POSTed despite the server's null/absent choice).
 */
import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../../api/client', () => ({ api: { get: apiMocks.get, post: apiMocks.post } }));
vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import useDoctorQueue from '../useDoctorQueue';

const CALLABLE_ENTRY = {
  id: 17,
  number: 'A017',
  patient_name: 'Синтетический Пациент',
  status: 'waiting',
  available_actions: ['call'],
  can_call: true,
};

function queuePayload(extra: Record<string, unknown>) {
  return {
    data: {
      entries: [CALLABLE_ENTRY],
      stats: { waiting: 1, called: 0, served: 0, total: 1 },
      can_call_next: true,
      queue_ids: [1],
      ...extra,
    },
  };
}

function postUrls(): Array<string> {
  return apiMocks.post.mock.calls.map(([url]) => String(url));
}

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
  apiMocks.post.mockResolvedValue({ data: { success: true } });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('QAPI-FE-001 (useDoctorQueue): the server null choice is not second-guessed', () => {
  it('explicit next_call_entry_id: null — callNext does NOT POST a guessed entry', async () => {
    apiMocks.get.mockResolvedValue(queuePayload({ next_call_entry_id: null }));

    const { result } = renderHook(() => useDoctorQueue('cardiology'));
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    let callResult: unknown;
    await act(async () => {
      callResult = await result.current.callNext();
    });

    expect((callResult as { success?: boolean }).success).toBe(false);
    expect(postUrls()).toEqual([]);
  });

  it('missing next_call_entry_id — fail closed, no POST', async () => {
    apiMocks.get.mockResolvedValue(queuePayload({}));

    const { result } = renderHook(() => useDoctorQueue('cardiology'));
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    let callResult: unknown;
    await act(async () => {
      callResult = await result.current.callNext();
    });

    expect((callResult as { success?: boolean }).success).toBe(false);
    expect(postUrls()).toEqual([]);
    // The published nextCallEntryId stays null — no guessed candidate.
    expect(result.current.nextCallEntryId).toBeNull();
  });

  it('a valid canonical id is called (positive control)', async () => {
    apiMocks.get.mockResolvedValue(queuePayload({ next_call_entry_id: 17 }));

    const { result } = renderHook(() => useDoctorQueue('cardiology'));
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.callNext();
    });

    expect(postUrls()).toEqual(['/doctor/queue/17/call']);
  });
});
