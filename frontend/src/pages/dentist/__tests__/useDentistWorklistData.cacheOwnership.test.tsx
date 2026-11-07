/**
 * Audit 3892 round 3 — fail-first regression for DENTCACHE-FE-001:
 * a slow older dentist-worklist request must never repopulate the module
 * cache or the panel state after the cache ownership was invalidated.
 * Cache invalidation (context switch, unmount) revokes the in-flight
 * loader's ownership; only the current epoch's response may commit.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';

import { useDentistWorklistData } from '../useDentistWorklistData';
import { dentistCache, invalidateDentistPanelCaches } from '../dentistContracts';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'test-token') },
}));

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

const queueResponseFor = (patientId: number) => ({
  status: 200,
  data: {
    queues: [{
      specialty: 'dentistry',
      entries: [{
        id: patientId * 10,
        patient_id: patientId,
        patient_name: `SYNTHETIC Patient ${patientId}`,
        visit_id: patientId * 100,
        status: 'waiting',
        discount_mode: 'none',
        services: [],
        service_codes: [],
        available_actions: [],
      }],
    }],
  },
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => { resolve = res; });
  return { promise, resolve };
};

beforeEach(() => {
  vi.clearAllMocks();
  invalidateDentistPanelCaches();
});

describe('useDentistWorklistData cache ownership (DENTCACHE-FE-001, audit 3892 round 3)', () => {
  it('a stale worklist response cannot repopulate the cache after invalidation', async () => {
    const a = deferred<{ status: number; data: unknown }>();
    vi.mocked(apiClient.get)
      .mockReturnValueOnce(a.promise as never)
      .mockResolvedValueOnce(queueResponseFor(9) as never);

    const { result } = renderHook(() => useDentistWorklistData({ tI18n: t, activeTab: 'appointments' }));

    // A's request is pending when the context switch invalidates the caches.
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));
    act(() => {
      invalidateDentistPanelCaches();
    });

    // B's fresh request resolves first and owns the cache.
    await act(async () => {
      void result.current.loadDentistryAppointments();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(dentistCache.appointments).toEqual([
      expect.objectContaining({ patient_id: 9 }),
    ]);

    // A's response arrives late — it must not overwrite B's cache or state.
    await act(async () => {
      a.resolve(queueResponseFor(7));
      await Promise.resolve();
    });
    expect(dentistCache.appointments).toEqual([
      expect.objectContaining({ patient_id: 9 }),
    ]);
    expect(result.current.appointmentsTableData).toEqual([
      expect.objectContaining({ patient_id: 9 }),
    ]);
    expect(result.current.patients).toEqual([
      expect.objectContaining({ patient_id: 9 }),
    ]);
  });

  it('an unmount-time invalidation also revokes the in-flight loader', async () => {
    const a = deferred<{ status: number; data: unknown }>();
    vi.mocked(apiClient.get).mockReturnValueOnce(a.promise as never);

    const { unmount } = renderHook(() =>
      useDentistWorklistData({ tI18n: t, activeTab: 'appointments' }));
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(1));

    // Unmount (logout/navigation) triggers the panel's cache invalidation.
    act(() => {
      invalidateDentistPanelCaches();
    });
    unmount();

    await act(async () => {
      a.resolve(queueResponseFor(7));
      await Promise.resolve();
    });
    expect(dentistCache.appointments).toBeNull();
  });
});
