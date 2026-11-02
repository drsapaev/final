/**
 * PR-UI-14-6 unit contract: useRefundRequests — the refund-request data
 * lifecycle + process commands moved verbatim from RefundRequestsTable.
 *
 * CSH-FE-011/012 (#3813) contract: the hook routes the list GET and the
 * process POST through the shared axios instance from api/client.ts —
 * never raw fetch(). The shared client owns the canonical /api/v1 base
 * URL, the Bearer header, X-CSRF-Token on the POST, single-flight 401
 * refresh and 429 cooldown; the hook owns status_filter and the payload.
 *
 * Pins:
 *  - list load calls api.get('/force-majeure/refund-requests', …) with
 *    status_filter only for non-'all' filters
 *  - no raw fetch() is issued (fail-first pin for the old origin-relative
 *    /force-majeure URL without /api/v1)
 *  - load result accepts both array and { requests } envelopes
 *  - process command posts { action, ...extraPayload } to the existing
 *    /process endpoint via api.post (never invented /approve|/reject|/complete URLs)
 *  - backend error detail is surfaced (shared getErrorMessage contract)
 *  - successful process reloads the list and calls onRefresh
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

const notifyMocks = vi.hoisted(() => ({
  error: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: apiMocks.get,
    post: apiMocks.post,
  },
}));

vi.mock('../../../services/notify', () => ({
  default: {
    error: notifyMocks.error,
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

import { useRefundRequests } from '../useRefundRequests';

const t = (key: string, options?: Record<string, unknown>) =>
  key + (options ? `:${JSON.stringify(options)}` : '');

// Raw global fetch must never fire: the shared client owns transport.
const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const axiosLikeError = (status: number, detail: string) => ({
  response: { status, data: { detail } },
});

beforeEach(() => {
  apiMocks.get.mockReset();
  apiMocks.post.mockReset();
  fetchMock.mockReset();
  notifyMocks.error.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useRefundRequests (PR-UI-14-6, CSH-FE-011/012 shared client)', () => {
  it('loads requests via the shared api client and never raw fetch', async () => {
    apiMocks.get.mockResolvedValueOnce({ data: [{ id: 1, status: 'pending' }] });
    const { result } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.requests).toEqual([{ id: 1, status: 'pending' }]);
    expect(apiMocks.get).toHaveBeenCalledTimes(1);
    expect(apiMocks.get.mock.calls[0][0]).toBe('/force-majeure/refund-requests');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('sends status_filter only for non-all filters', async () => {
    apiMocks.get.mockResolvedValue({ data: [] });
    const { result, rerender } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(apiMocks.get.mock.calls[0][1]).toEqual({ params: {} });

    result.current.setFilter('approved');
    rerender();
    await waitFor(() => expect(apiMocks.get.mock.calls.length).toBeGreaterThanOrEqual(2));
    expect(apiMocks.get.mock.calls[1][1]).toEqual({ params: { status_filter: 'approved' } });
  });

  it('accepts the { requests } envelope shape', async () => {
    apiMocks.get.mockResolvedValueOnce({ data: { requests: [{ id: 2 }] } });
    const { result } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.requests).toEqual([{ id: 2 }]));
  });

  it('process posts { action, ...extraPayload } via api.post to the /process endpoint and reloads', async () => {
    apiMocks.get.mockResolvedValue({ data: [] });
    const onRefresh = vi.fn();
    const { result } = renderHook(() => useRefundRequests(t, onRefresh));
    await waitFor(() => expect(result.current.loading).toBe(false));

    apiMocks.post.mockResolvedValueOnce({ data: { ok: true } });

    await result.current.handleReject(7, 'причина');

    expect(apiMocks.post).toHaveBeenCalledTimes(1);
    const [url, payload] = apiMocks.post.mock.calls[0] as [string, Record<string, unknown>];
    expect(url).toBe('/force-majeure/refund-requests/7/process');
    expect(payload).toEqual({ action: 'reject', rejection_reason: 'причина' });
    // CSRF on the POST is the shared client's job — the hook must not
    // hand-build headers.
    expect(apiMocks.post.mock.calls[0].length).toBe(2);
    await waitFor(() => expect(onRefresh).toHaveBeenCalled());
    // reload after the command
    expect(apiMocks.get.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('failed load surfaces the backend detail through the shared error contract', async () => {
    apiMocks.get.mockRejectedValueOnce(axiosLikeError(500, 'БД недоступна'));
    const { result } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toContain('БД недоступна');
    expect(result.current.requests).toEqual([]);
  });

  it('failed process surfaces the backend detail and clears processingId', async () => {
    apiMocks.get.mockResolvedValue({ data: [] });
    const { result } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.loading).toBe(false));

    apiMocks.post.mockRejectedValueOnce(axiosLikeError(403, 'Недостаточно прав'));

    await result.current.handleApprove(9);

    expect(result.current.processingId).toBeNull();
    expect(notifyMocks.error).toHaveBeenCalledTimes(1);
    expect(notifyMocks.error.mock.calls[0][0]).toContain('Недостаточно прав');
    // the list is NOT reloaded after a failed command and onRefresh is not fired
    expect(apiMocks.get).toHaveBeenCalledTimes(1);
  });
});
