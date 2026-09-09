/**
 * Contract tests for sw.template.js caching rules.
 *
 * NO_CACHE_PATTERNS (payments, ai, telegram, print, auth) must never be
 * written to Cache Storage: on a shared clinic computer the offline
 * fallback could otherwise serve one user's API responses to another.
 * Regression guard — the denylist existed but was not consulted by the
 * fetch handler.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it, vi } from 'vitest';

type SWRequest = { url: string; method?: string };

type SWInternals = {
  networkFirst: (
    request: SWRequest,
    cacheName: string,
    offlineFallbackUrl?: string,
  ) => Promise<{ ok: boolean }>;
  isNoCachePath: (pathname: string) => boolean;
  syncClinicData: () => Promise<void>;
};

// vitest cwd is the frontend/ directory (see vitest.config.ts root note)
const TEMPLATE_PATH = path.resolve(process.cwd(), 'sw.template.js');

type CacheStubs = {
  put: ReturnType<typeof vi.fn>;
  caches: { open: ReturnType<typeof vi.fn>; match: ReturnType<typeof vi.fn> };
};

function makeCacheStubs(): CacheStubs {
  const put = vi.fn();
  const cache = { put, match: vi.fn(async () => undefined) };
  return { put, caches: { open: vi.fn(async () => cache), match: vi.fn(async () => undefined) } };
}

function compileSW(
  fetchImpl: ReturnType<typeof vi.fn>,
  cachesStub: CacheStubs['caches'],
): SWInternals {
  const code = readFileSync(TEMPLATE_PATH, 'utf8');
  const factory = new Function(
    'self',
    'caches',
    'location',
    'clients',
    'console',
    'fetch',
    `${code}\nreturn { networkFirst, isNoCachePath, syncClinicData };`,
  );
  return factory(
    { addEventListener: vi.fn(), skipWaiting: vi.fn(), registration: {} },
    cachesStub,
    { origin: 'https://clinic.test' },
    {},
    { log: vi.fn(), warn: vi.fn(), error: vi.fn() },
    fetchImpl,
  ) as SWInternals;
}

const okResponse = () => ({ ok: true, clone() { return this; } });

describe('sw.template.js NO_CACHE_PATTERNS enforcement', () => {
  it.each([
    '/api/v1/payments/test',
    '/api/v1/payments/42/invoice',
    '/api/v1/ai/suggestions',
    '/api/v1/telegram/webhook',
    '/api/v1/print/visit/1',
    '/api/v1/auth/me',
  ])('does not cache a successful GET of %s', async (pathname) => {
    const { put, caches } = makeCacheStubs();
    const sw = compileSW(vi.fn(async () => okResponse()), caches);
    const res = await sw.networkFirst({ url: `https://clinic.test${pathname}` }, 'DYNAMIC_CACHE');
    expect(res.ok).toBe(true);
    expect(put).not.toHaveBeenCalled();
  });

  it('still returns the network response when caching is skipped', async () => {
    const { put, caches } = makeCacheStubs();
    const response = okResponse();
    const sw = compileSW(vi.fn(async () => response), caches);
    const res = await sw.networkFirst(
      { url: 'https://clinic.test/api/v1/payments/test' },
      'DYNAMIC_CACHE',
    );
    expect(res).toBe(response);
    expect(put).not.toHaveBeenCalled();
  });

  it('still caches successful GETs for cacheable API endpoints (offline contract intact)', async () => {
    const { put, caches } = makeCacheStubs();
    const sw = compileSW(vi.fn(async () => okResponse()), caches);
    await sw.networkFirst({ url: 'https://clinic.test/api/v1/patients' }, 'DYNAMIC_CACHE');
    expect(put).toHaveBeenCalledTimes(1);
  });

  it('offline fallback still serves previously cached data for cacheable endpoints', async () => {
    const stubs = makeCacheStubs();
    const cached = { ok: true };
    stubs.caches.match = vi.fn(async () => cached);
    const sw = compileSW(vi.fn(async () => { throw new Error('offline'); }), stubs.caches);
    const res = await sw.networkFirst({ url: 'https://clinic.test/api/v1/patients' }, 'DYNAMIC_CACHE');
    expect(res).toBe(cached);
  });

  it('does not serve a cached sensitive response offline because it was never stored', async () => {
    const stubs = makeCacheStubs();
    stubs.caches.match = vi.fn(async () => undefined);
    const sw = compileSW(vi.fn(async () => { throw new Error('offline'); }), stubs.caches);
    await expect(
      sw.networkFirst({ url: 'https://clinic.test/api/v1/payments/test' }, 'DYNAMIC_CACHE'),
    ).rejects.toThrow('offline');
  });

  it('isNoCachePath matches every declared denylist pattern and nothing else', () => {
    const sw = compileSW(vi.fn(), makeCacheStubs().caches);
    expect(sw.isNoCachePath('/api/v1/auth/login')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/auth/logout')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/auth/me')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/payments/1')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/ai/chat')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/telegram/send')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/print/x')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/patients')).toBe(false);
    expect(sw.isNoCachePath('/api/v1/queue')).toBe(false);
  });

  it('background sync never fetches or caches the user profile (auth/me)', async () => {
    const { put, caches } = makeCacheStubs();
    const fetchedUrls: string[] = [];
    const fetchImpl = vi.fn(async (input: string | { url?: string }) => {
      const url = typeof input === 'string' ? input : (input.url ?? '');
      fetchedUrls.push(url);
      return okResponse();
    });
    const sw = compileSW(fetchImpl, caches);

    await sw.syncClinicData();

    expect(fetchedUrls).not.toContain('/api/v1/auth/me');
    const putUrls = put.mock.calls.map((call) => {
      const req = call[0] as string | { url?: string };
      return typeof req === 'string' ? req : (req.url ?? '');
    });
    expect(putUrls).not.toContain('/api/v1/auth/me');
  });
});
