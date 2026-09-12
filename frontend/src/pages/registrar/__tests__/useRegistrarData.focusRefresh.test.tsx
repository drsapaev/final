/**
 * RQ-27.a (F-23, S-28) — cross-session reference-data revalidation.
 *
 * Window events (`departments:updated` / `queue-profiles:updated`) never
 * cross browser contexts: when an administrator creates/renames/disables a
 * department or profile in ANOTHER session, this registrar session used to
 * keep stale doctors/services/departments until a full page reload — the
 * only in-app paths were the same-session events and the post-wizard reload.
 *
 * The fix: when the user returns to the session (visibilitychange → visible,
 * window focus), the hook silently revalidates the reference data. The
 * revalidation must behave like the RQ-22 worklist silent refresh — previous
 * data stays on screen while the fetch is in flight AND after a failure
 * (no wipe, no error toast) — while the NON-silent paths keep the original
 * cleared-before-fetch semantics byte-for-byte.
 *
 * A 5s throttle collapses the focus+visibilitychange burst browsers fire
 * together into one revalidation (extra-requests budget per S-28).
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRegistrarData } from '../useRegistrarData';
import { api } from '../../../api/client';
import notify from '../../../services/notify';

vi.mock('../../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../../services/notify', () => ({ default: { error: vi.fn(), success: vi.fn() } }));
vi.mock('../../../utils/logger', () => ({ default: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), log: vi.fn() } }));
vi.mock('../../../utils/tokenManager', () => ({ default: { getAccessToken: () => 'test-token' } }));

const DOCTORS_RESPONSE = { data: { doctors: [{ id: 7, full_name: 'SYNTHETIC Doctor' }] } };
const SERVICES_RESPONSE = { data: { services_by_group: { consultation: [{ id: 3, name: 'SYNTHETIC Service' }] } } };
const DEPARTMENTS_RESPONSE = { data: { data: [{ id: 11, name: 'SYNTHETIC Dept' }] } };

const mockCatalogSuccess = () => {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === '/registrar/doctors') return DOCTORS_RESPONSE;
    if (url === '/registrar/services') return SERVICES_RESPONSE;
    if (url === '/registrar/departments?active_only=true') return DEPARTMENTS_RESPONSE;
    throw new Error(`unexpected url ${url}`);
  });
};

const setDocumentVisibility = (value: Document['visibilityState']) => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => value });
};

const fireVisibilityChange = () => {
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'));
  });
};

const fireWindowFocus = () => {
  act(() => {
    window.dispatchEvent(new Event('focus'));
  });
};

const catalogCallCount = () =>
  vi.mocked(api.get).mock.calls.filter(([url]) =>
    url === '/registrar/doctors' || url === '/registrar/services' || url === '/registrar/departments?active_only=true',
  ).length;

describe('useRegistrarData — RQ-27.a cross-session silent revalidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCatalogSuccess();
    setDocumentVisibility('visible');
  });

  afterEach(() => {
    setDocumentVisibility('visible');
  });

  it('revalidates the catalog silently when the session becomes visible again', async () => {
    const { result } = renderHook(() => useRegistrarData());

    // Initial (non-silent) load via the regular entry point.
    await act(async () => {
      await result.current.loadIntegratedData();
    });
    expect(catalogCallCount()).toBe(3);
    expect(result.current.doctors).toHaveLength(1);

    // The window-event path of ANOTHER session is not visible here — the
    // catalog would stay stale forever. Returning to the session must
    // trigger a silent revalidation (3 fresh requests).
    fireVisibilityChange();

    await waitFor(() => {
      expect(catalogCallCount()).toBe(6);
    });
    expect(result.current.doctors).toHaveLength(1);
    expect(notify.error).not.toHaveBeenCalled();
  });

  it('revalidates on window focus and throttles the focus+visibility burst to one refresh', async () => {
    const { result } = renderHook(() => useRegistrarData());

    await act(async () => {
      await result.current.loadIntegratedData();
    });
    expect(catalogCallCount()).toBe(3);

    // Browsers fire focus + visibilitychange together when returning to the
    // tab/window: the burst must collapse into ONE revalidation.
    fireWindowFocus();
    fireVisibilityChange();

    await waitFor(() => {
      expect(catalogCallCount()).toBe(6);
    });
    // Give any (wrong) second burst a chance to fire.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(catalogCallCount()).toBe(6);
  });

  it('keeps previous reference data and stays quiet when the silent revalidation fails', async () => {
    const { result } = renderHook(() => useRegistrarData());

    await act(async () => {
      await result.current.loadIntegratedData();
    });
    expect(result.current.doctors).toHaveLength(1);

    vi.mocked(api.get).mockRejectedValue(new Error('network down during revalidation'));
    fireVisibilityChange();

    await waitFor(() => {
      expect(catalogCallCount()).toBe(6);
    });
    // RQ-22 philosophy: a failed refresh must NOT wipe previously loaded
    // reference data into an empty panel, and must not spam an error toast
    // for a background revalidation.
    expect(result.current.doctors).toHaveLength(1);
    expect(notify.error).not.toHaveBeenCalled();
  });

  it('does not revalidate while the document is hidden', async () => {
    const { result } = renderHook(() => useRegistrarData());

    await act(async () => {
      await result.current.loadIntegratedData();
    });
    expect(catalogCallCount()).toBe(3);

    setDocumentVisibility('hidden');
    fireVisibilityChange();
    fireWindowFocus();

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(catalogCallCount()).toBe(3);
  });

  it('keeps the non-silent cleared-before-fetch contract byte-for-byte', async () => {
    const { result } = renderHook(() => useRegistrarData());

    await act(async () => {
      await result.current.loadIntegratedData();
    });
    expect(result.current.doctors).toHaveLength(1);

    // Direct (non-silent) call with a failing backend: the original contract
    // clears the state before fetching (set only on success), so a failure
    // leaves the panel reference data empty — in contrast to the silent
    // revalidation above, which keeps previous data.
    vi.mocked(api.get).mockRejectedValue(new Error('backend unavailable'));
    await act(async () => {
      await result.current.loadIntegratedData();
    });

    expect(result.current.doctors).toHaveLength(0);
    expect(result.current.services).toEqual({});
    expect(result.current.dynamicDepartments).toHaveLength(0);
    // The notify.error path is only reachable for exceptions outside the
    // allSettled block (pre-existing behavior, unchanged by RQ-27.a).
    expect(notify.error).not.toHaveBeenCalled();
  });
});
