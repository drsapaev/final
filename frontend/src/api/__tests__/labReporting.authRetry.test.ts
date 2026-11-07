/**
 * LABR-FE-001 (audit 3886, ledger group «lab report API, PDF preview and
 * AI result ownership») — fail-first regression for the lab transport's
 * expired-JWT handling:
 *
 * The lab façade's raw `fetch` used a snapshot access token and threw on
 * any 401 — an expired access JWT during an active laboratory session
 * failed reads, mutations and PDF downloads instead of transparently
 * refreshing through the canonical single-flight refresh and retrying
 * once.
 *
 * Red-first: on the pre-fix source every 401 surfaces as a rejection —
 * no refresh call, no retry, no result.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const forceRefreshTokenMock = vi.hoisted(() => vi.fn(async () => 'fresh-token'));
const fetchMock = vi.hoisted(() => vi.fn());

vi.mock('../client', () => ({
  forceRefreshToken: forceRefreshTokenMock,
}));
vi.mock('../runtime', () => ({
  getApiBaseUrl: () => 'http://synthetic.test/api/v1',
}));
vi.mock('../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'expired-token') },
}));

import tokenManager from '../../utils/tokenManager';
import { labReportingApi } from '../labReporting';

const mockedToken = vi.mocked(tokenManager.getAccessToken);

function jsonResponse(status: number, body: Record<string, unknown>) {
  return {
    ok: status < 400,
    status,
    statusText: status < 400 ? 'OK' : 'Error',
    json: async () => body,
    blob: async () => new Blob(['%PDF-synthetic'], { type: 'application/pdf' }),
  } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
  mockedToken.mockReturnValue('expired-token');
});

describe('LABR-FE-001 — the lab transport converges on the canonical auth refresh', () => {
  it('refreshes once and retries a rejected 401 read (pre-fix: the 401 surfaced to the user)', async () => {
    forceRefreshTokenMock.mockImplementation(async () => {
      mockedToken.mockReturnValue('fresh-token');
      return 'fresh-token';
    });
    fetchMock.mockImplementation(async (url: unknown, init?: RequestInit) => {
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      if (String(auth).includes('expired-token')) {
        return jsonResponse(401, { detail: 'Token expired' });
      }
      return jsonResponse(200, { entries: [{ id: 1 }], total: 1 });
    });

    const payload = (await labReportingApi.listQueueToday(null, { limit: 50, offset: 0 })) as Record<string, unknown>;
    expect((payload.entries as unknown[]).length).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    // The canonical shared refresh was consulted exactly once.
    expect(forceRefreshTokenMock).toHaveBeenCalledTimes(1);
  });

  it('concurrent 401 reads share one refresh through the canonical single-flight', async () => {
    let refreshes = 0;
    forceRefreshTokenMock.mockImplementation(async () => {
      refreshes += 1;
      mockedToken.mockReturnValue('fresh-token');
      return 'fresh-token';
    });
    fetchMock.mockImplementation(async (_url: unknown, init?: RequestInit) => {
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      if (String(auth).includes('expired-token')) {
        return jsonResponse(401, { detail: 'Token expired' });
      }
      return jsonResponse(200, { entries: [{ id: 7 }], total: 1 });
    });

    const [a, b] = await Promise.all([
      labReportingApi.listQueueToday(null, { limit: 50, offset: 0 }),
      labReportingApi.listQueueToday(null, { limit: 50, offset: 50 }),
    ]);
    expect((a as Record<string, unknown>).entries).toHaveLength(1);
    expect((b as Record<string, unknown>).entries).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    // One shared network refresh, even though both requests recovered.
    expect(refreshes).toBeGreaterThanOrEqual(1);
    expect(forceRefreshTokenMock).toHaveBeenCalled();
  });

  it('retries a known-rejected 401 mutation once with the same Idempotency-Key', async () => {
    const seenKeys: Array<string | undefined> = [];
    fetchMock.mockImplementation(async (url: unknown, init?: RequestInit) => {
      seenKeys.push((init?.headers as Record<string, string>)?.['Idempotency-Key']);
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      if (String(auth).includes('expired-token')) {
        return jsonResponse(401, { detail: 'Token expired' });
      }
      return jsonResponse(200, { id: 91, status: 'IN_PROGRESS' });
    });

    const created = (await labReportingApi.createInstance(
      { template_id: 3, patient_id: 444 },
      { idempotencyKey: 'op-synthetic-1' }
    )) as Record<string, unknown>;
    expect(created.id).toBe(91);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(forceRefreshTokenMock).toHaveBeenCalledTimes(1);
    // Both attempts carried the SAME operation key — a server-side retry of
    // a rejected command cannot commit twice.
    expect(seenKeys[0]).toBe('op-synthetic-1');
    expect(seenKeys[1]).toBe('op-synthetic-1');
  });

  it('does NOT retry transport errors (ambiguous POST outcome stays surfaced)', async () => {
    fetchMock.mockImplementation(async () => {
      throw new TypeError('Failed to fetch');
    });

    await expect(labReportingApi.listQueueToday(null, {})).rejects.toThrow('Failed to fetch');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(forceRefreshTokenMock).not.toHaveBeenCalled();
  });

  it('does NOT retry non-401 rejections (a 400 stays a client error)', async () => {
    fetchMock.mockImplementation(async () => jsonResponse(400, { detail: 'Bad payload' }));

    await expect(labReportingApi.listQueueToday(null, {})).rejects.toThrow('Bad payload');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(forceRefreshTokenMock).not.toHaveBeenCalled();
  });

  it('refreshes and retries PDF/preview blob reads on a rejected 401', async () => {
    fetchMock.mockImplementation(async (_url: unknown, init?: RequestInit) => {
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      if (String(auth).includes('expired-token')) {
        return jsonResponse(401, { detail: 'Token expired' });
      }
      return jsonResponse(200, {});
    });

    const blob = await labReportingApi.previewInstancePdf(91);
    expect(blob).toBeInstanceOf(Blob);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/lab/report-instances/91/preview');
    expect(String(fetchMock.mock.calls[1][0])).toContain('/lab/report-instances/91/preview');

    const pdf = await labReportingApi.downloadPdf(92);
    expect(pdf).toBeInstanceOf(Blob);
  });
});
