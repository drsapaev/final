import fs from 'fs';
import path from 'path';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fileURLToPath } from 'node:url';
import { labReportingApi } from '../labReporting';

vi.mock('../client', () => ({ forceRefreshToken: vi.fn() }));
vi.mock('../runtime', () => ({ getApiBaseUrl: () => 'http://synthetic.test/api/v1' }));
vi.mock('../../utils/tokenManager', () => ({
  default: { getAccessToken: () => 'synthetic-access-token' },
}));

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

const source = fs.readFileSync(
  path.join(ROOT, 'api/labReporting.ts'),
  'utf8'
);

describe('labReportingApi UX-AUDIT-FIX12 — AbortController support', () => {
  it('request() forwards options.signal to fetch', () => {
    // FIX12: request() должен пробрасывать signal в fetch.
    expect(source).toContain('UX-AUDIT-FIX12');
    expect(source).toContain('options.signal');
    expect(source).toContain('signal: options.signal');
  });

  it('documents the AbortController contract in JSDoc', () => {
    // Документация должна объяснять, как вызывающий код использует signal.
    expect(source).toContain('AbortSignal');
    expect(source).toContain('AbortController');
  });

  it('preserves existing request signature (path, options)', () => {
    // Backward-compat: существующие вызовы без signal продолжают работать.
    // Phase 1 TS migration: signature now has type annotations.
    expect(source).toMatch(/async function request\(path[^,]*,\s*options[^=]*=\s*\{\s*\}\)/);
  });

  it('uses spread operator to pass signal conditionally', () => {
    // signal должен быть опциональным — если не передан, fetch работает без него.
    expect(source).toContain("...(options.signal ? { signal: options.signal } : {})");
  });

  it('STRAT#4: listQueueToday accepts server-side pagination params', () => {
    // FIX: listQueueToday ранее принимал только targetDate. Теперь принимает
    // второй аргумент params = { limit, offset } для server-side pagination.
    expect(source).toContain('STRAT#4');
    // Phase 1 TS migration: params now have type annotations. Match the
    // signature either without (JS) or with (TS) type annotations on both
    // targetDate and params.
    expect(source).toMatch(/listQueueToday\(targetDate(?:\s*:[^=]+)?\s*=\s*null,\s*params(?:\s*:[^=]+)?\s*=\s*\{\s*\}\)/);
    // limit и offset пробрасываются в query string
    expect(source).toContain("params.limit !== undefined");
    expect(source).toContain("search.set('limit', String(params.limit))");
    expect(source).toContain("params.offset !== undefined");
    expect(source).toContain("search.set('offset', String(params.offset))");
  });
});

describe('labReportingApi report creation reconciliation', () => {
  const createUrl = 'http://synthetic.test/api/v1/lab/report-instances';
  const idempotencyKey = 'synthetic-report-creation';
  const fetchMock = vi.fn<typeof globalThis.fetch>();
  const request = { patient_id: '44', template_id: 3, service_codes: ['SYNTHETIC'] };
  const report = {
    id: 91,
    patient_id: 44,
    template_id: 3,
    status: 'DRAFT',
    updated_at: '2026-11-24T08:00:00.123456Z',
    sections: [],
  };

  const jsonResponse = (status: number, body: unknown) => new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it.each([
    { cause: 'network failure', response: async () => { throw new TypeError('Connection lost'); } },
    { cause: 'invalid JSON', response: async () => new Response('{', { status: 200 }) },
    { cause: 'gateway error', response: async () => jsonResponse(502, { detail: 'Bad gateway' }) },
    {
      cause: 'uncertain outcome',
      response: async () => jsonResponse(409, {
        detail: 'Prior outcome unknown',
        code: 'idempotency_uncertain_outcome',
      }),
    },
    {
      cause: 'concurrent operation',
      response: async () => jsonResponse(409, {
        detail: 'Same request is still executing',
        code: 'idempotency_in_flight',
      }),
    },
  ])('recovers the exact committed request after $cause', async ({ response }) => {
    const payload = { ...request, service_codes: [...request.service_codes] };
    fetchMock
      .mockImplementationOnce(async () => {
        payload.patient_id = '52';
        payload.service_codes.push('SYNTHETIC-LATER-EDIT');
        return response();
      })
      .mockResolvedValueOnce(jsonResponse(200, report));

    await expect(labReportingApi.createInstance(payload, { idempotencyKey })).resolves.toEqual(report);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(1, createUrl, expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(request),
      headers: expect.objectContaining({ 'Idempotency-Key': idempotencyKey }),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, `${createUrl}/creation-result`, expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ idempotency_key: idempotencyKey, request }),
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer synthetic-access-token' },
      signal: expect.any(AbortSignal),
    }));
  });

  it.each([404, 503])('preserves the original failure when recovery responds %s', async (status) => {
    const originalError = new TypeError('Original response was lost');
    fetchMock.mockRejectedValueOnce(originalError)
      .mockResolvedValueOnce(jsonResponse(status, { detail: 'Recovery unavailable' }));

    await expect(labReportingApi.createInstance(request, { idempotencyKey })).rejects.toBe(originalError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([
    { issue: 'missing report', body: { id: 91 } },
    { issue: 'different patient', body: { ...report, patient_id: 45 } },
    { issue: 'missing patient', body: { ...report, patient_id: undefined } },
    { issue: 'missing version', body: { ...report, updated_at: undefined } },
    { issue: 'blank version', body: { ...report, updated_at: ' ' } },
  ])('preserves the original error for a recovery response with $issue', async ({ body }) => {
    const originalError = new TypeError('Original response was lost');
    fetchMock.mockRejectedValueOnce(originalError).mockResolvedValueOnce(jsonResponse(200, body));

    await expect(labReportingApi.createInstance(request, { idempotencyKey })).rejects.toBe(originalError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('returns the original failure when recovery times out', async () => {
    vi.useFakeTimers();
    const originalError = new TypeError('Original response was lost');
    fetchMock.mockRejectedValueOnce(originalError)
      .mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true });
      }));

    const outcome = expect(labReportingApi.createInstance(request, { idempotencyKey }))
      .rejects.toBe(originalError);
    await vi.advanceTimersByTimeAsync(25_000);
    await outcome;
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('preserves a payload mismatch without requesting recovery', async () => {
    const code = 'idempotency_payload_mismatch';
    const detail = 'Idempotency key was already used with a different request';
    fetchMock.mockResolvedValueOnce(jsonResponse(409, { code, detail }));

    await expect(labReportingApi.createInstance(request, { idempotencyKey })).rejects.toMatchObject({
      message: detail,
      status: 409,
      code,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not attempt recovery for unkeyed creation', async () => {
    const originalError = new TypeError('Original response was lost');
    fetchMock.mockRejectedValueOnce(originalError);

    await expect(labReportingApi.createInstance(request)).rejects.toBe(originalError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
