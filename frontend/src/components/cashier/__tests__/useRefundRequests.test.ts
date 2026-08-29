/**
 * PR-UI-14-6 unit contract: useRefundRequests — the refund-request data
 * lifecycle + process commands moved verbatim from RefundRequestsTable.
 *
 * Pins:
 *  - list load sends status_filter only for non-'all' filters
 *  - load result accepts both array and { requests } envelopes
 *  - process command posts { action, ...extraPayload } to the existing
 *    /process endpoint (never invented /approve|/reject|/complete URLs)
 *  - successful process reloads the list and calls onRefresh
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

import { useRefundRequests } from '../useRefundRequests';

const t = (key: string, options?: Record<string, unknown>) =>
  key + (options ? `:${JSON.stringify(options)}` : '');

const fetchMock = vi.fn();

vi.stubGlobal('fetch', fetchMock);

beforeEach(() => {
  fetchMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useRefundRequests (PR-UI-14-6)', () => {
  it('loads requests on mount and sends status_filter only for non-all filters', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ([{ id: 1, status: 'pending' }]),
    });
    const { result } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.requests).toEqual([{ id: 1, status: 'pending' }]);
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url.startsWith('/force-majeure/refund-requests?')).toBe(true);
    expect(url).not.toContain('status_filter');
  });

  it('accepts the { requests } envelope shape', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ requests: [{ id: 2 }] }),
    });
    const { result } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.requests).toEqual([{ id: 2 }]));
  });

  it('process posts { action, ...extraPayload } to the /process endpoint and reloads', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] });
    const onRefresh = vi.fn();
    const { result } = renderHook(() => useRefundRequests(t, onRefresh));
    await waitFor(() => expect(result.current.loading).toBe(false));

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] }); // process
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] }); // reload

    await result.current.handleReject(7, 'причина');

    const processCall = fetchMock.mock.calls[1];
    expect(String(processCall[0])).toBe('/force-majeure/refund-requests/7/process');
    const init = processCall[1] as { method: string; body: string };
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ action: 'reject', rejection_reason: 'причина' });
    await waitFor(() => expect(onRefresh).toHaveBeenCalled());
  });

  it('failed load surfaces the error state', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'));
    const { result } = renderHook(() => useRefundRequests(t));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('network down');
    expect(result.current.requests).toEqual([]);
  });
});
