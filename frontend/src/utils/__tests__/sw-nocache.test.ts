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

type SWRequest = {
  url: string;
  method?: string;
  mode?: string;
  headers?: { get: (name: string) => string | null };
};

type SWInternals = {
  handleRequest: (request: SWRequest) => Promise<Response>;
  purgeSensitiveEntries: () => Promise<void>;
  handlers: Map<string, (event: { data?: unknown; waitUntil: (value: Promise<unknown>) => void }) => void>;
  networkFirst: (
    request: SWRequest,
    cacheName: string,
    offlineFallbackUrl?: string,
  ) => Promise<{ ok: boolean }>;
  isNoCachePath: (pathname: string) => boolean;
  staticFiles: string[];
  syncClinicData: () => Promise<void>;
};

// vitest cwd is the frontend/ directory (see vitest.config.ts root note)
const TEMPLATE_PATH = path.resolve(process.cwd(), 'sw.template.js');

type CacheStubs = {
  put: ReturnType<typeof vi.fn>;
  caches: { open: ReturnType<typeof vi.fn>; match: ReturnType<typeof vi.fn>; keys: ReturnType<typeof vi.fn> };
};

function makeCacheStubs(): CacheStubs {
  const put = vi.fn();
  const cache = { put, match: vi.fn(async () => undefined), delete: vi.fn(), keys: vi.fn(async () => []) };
  return { put, caches: { open: vi.fn(async () => cache), match: vi.fn(async () => undefined), keys: vi.fn(async () => []) } };
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
    `${code}\nreturn { handleRequest, networkFirst, isNoCachePath, purgeSensitiveEntries, syncClinicData, staticFiles: STATIC_FILES };`,
  );
  const handlers = new Map();
  const result = factory(
    { addEventListener: (name: string, handler: unknown) => { if (!handlers.has(name)) handlers.set(name, handler); }, skipWaiting: vi.fn(), registration: {}, clients: { claim: vi.fn() } },
    cachesStub,
    { origin: 'https://clinic.test' },
    {},
    { log: vi.fn(), warn: vi.fn(), error: vi.fn() },
    fetchImpl,
  );
  return { ...result, handlers } as SWInternals;
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
    '/api/v1/public-site/services',
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

  it.each([
    '/api/v1/auth/me',
    '/api/v1/public-site/services?locale=ru',
  ])('does not replay a pre-existing no-cache response through the outer offline handler: %s', async (path) => {
    const stubs = makeCacheStubs();
    stubs.caches.match = vi.fn(async () => new Response('private cached profile'));
    const sw = compileSW(vi.fn(async () => { throw new Error('offline'); }), stubs.caches);

    const response = await sw.handleRequest({
      url: `https://clinic.test${path}`,
      method: 'GET',
      mode: 'cors',
      headers: { get: () => null },
    });

    expect(response.status).toBe(503);
    expect(await response.text()).toBe('Нет подключения к интернету');
    expect(stubs.caches.match).not.toHaveBeenCalled();
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
    expect(sw.isNoCachePath('/api/v1/public-site/services')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/public-site/doctors/synthetic-profile')).toBe(true);
    expect(sw.isNoCachePath('/api/v1/patients')).toBe(false);
    expect(sw.isNoCachePath('/api/v1/queue')).toBe(false);
  });

  it.each([
    '/',
    '/ru',
    '/ru/services',
    '/ru/doctors/dermatolog',
    '/services',
    '/services/skin-care',
    '/doctors',
    '/prices',
    '/contacts',
    '/sitemap.xml',
  ])('does not cache public HTML or sitemap at %s', (pathname) => {
    const sw = compileSW(vi.fn(), makeCacheStubs().caches);
    expect(sw.isNoCachePath(pathname)).toBe(true);
  });

  it('does not keep the dynamically rendered public root in the install cache', () => {
    const sw = compileSW(vi.fn(), makeCacheStubs().caches);
    expect(sw.staticFiles).not.toContain('/');
  });

  it('does not replay an older public page when a navigation fails offline', async () => {
    const stalePage = { html: 'old published card' };
    const offlinePage = { html: 'offline fallback' };
    const stubs = makeCacheStubs();
    stubs.caches.match = vi.fn(async (key: unknown) =>
      key === '/offline.html' ? offlinePage : stalePage,
    );
    const sw = compileSW(vi.fn(async () => { throw new Error('offline'); }), stubs.caches);

    await expect(
      sw.networkFirst(
        { url: 'https://clinic.test/services/skin-care' },
        'DYNAMIC_CACHE',
        '/offline.html',
      ),
    ).resolves.toBe(offlinePage);
    expect(stubs.caches.match).toHaveBeenCalledTimes(1);
    expect(stubs.caches.match).toHaveBeenCalledWith('/offline.html');
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

  it.each([
    '/reset-password?token=SYNTHETIC_SECRET',
    '/RESET-PASSWORD/?token=SYNTHETIC_SECRET',
    '/%72eset-password?token=SYNTHETIC_SECRET',
    '/api/v1/password-reset/validate-token',
    '/api/v1/password-reset/fake.js',
    '/confirm-visit?%74oken=SYNTHETIC_SECRET',
  ])('never persists or replays a sensitive request: %s', async (pathname) => {
    const request = {
      url: `https://clinic.test${pathname}`,
      method: 'GET', mode: 'cors', headers: new Headers(),
    };
    const stubs = makeCacheStubs();
    const online = compileSW(vi.fn(async () => new Response('network')), stubs.caches);
    expect(await (await online.handleRequest(request)).text()).toBe('network');
    expect(stubs.put).not.toHaveBeenCalled();

    stubs.caches.match = vi.fn(async () => new Response('STALE_OTHER_PATIENT'));
    const offline = compileSW(vi.fn(async () => { throw new Error('offline'); }), stubs.caches);
    const response = await offline.handleRequest(request);
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain('STALE_OTHER_PATIENT');
    expect(stubs.caches.match).not.toHaveBeenCalled();
  });

  it('never caches or replays an alternate endpoint carrying a reset-token header', async () => {
    const stubs = makeCacheStubs();
    stubs.caches.match = vi.fn(async () => new Response('OTHER_TOKEN_RESPONSE'));
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(new Response('LIVE'))
      .mockRejectedValueOnce(new Error('offline'));
    const sw = compileSW(fetchImpl, stubs.caches);
    const request = {
      url: 'https://clinic.test/api/v1/alternate', method: 'GET', mode: 'cors',
      headers: new Headers({ 'X-Reset-Token': 'SYNTHETIC_PROOF' }),
    };
    expect(await (await sw.handleRequest(request)).text()).toBe('LIVE');
    expect((await sw.handleRequest(request)).status).toBe(503);
    expect(stubs.put).not.toHaveBeenCalled();
    expect(stubs.caches.match).not.toHaveBeenCalled();
  });

  it('uses only the generic offline page for a sensitive navigation', async () => {
    const stubs = makeCacheStubs();
    stubs.caches.match = vi.fn(async (key: unknown) =>
      key === '/offline.html' ? new Response('OFFLINE_PAGE') : new Response('STALE_RESET_PAGE'));
    const sw = compileSW(vi.fn(async () => { throw new Error('offline'); }), stubs.caches);
    const response = await sw.handleRequest({
      url: 'https://clinic.test/reset-password?token=SYNTHETIC_SECRET',
      method: 'GET', mode: 'navigate', headers: new Headers({ accept: 'text/html' }),
    });
    expect(await response.text()).toBe('OFFLINE_PAGE');
    expect(stubs.caches.match).toHaveBeenCalledTimes(1);
    expect(stubs.caches.match).toHaveBeenCalledWith('/offline.html');
  });

  it('purges only previously stored credential-bearing entries from clinic caches', async () => {
    const stubs = makeCacheStubs();
    const entries = [
      new Request('https://clinic.test/reset-password?token=SYNTHETIC_SECRET'),
      new Request('https://clinic.test/api/v1/password-reset/validate-token'),
      new Request('https://clinic.test/confirm-visit?%74oken=SYNTHETIC_SECRET'),
      new Request('https://clinic.test/api/v1/patients'),
    ];
    const remove = vi.fn(async (_request: Request) => true);
    stubs.caches.keys = vi.fn(async () => ['clinic-offline-queue', 'clinic-offline-data', 'other-app']);
    stubs.caches.open = vi.fn(async () => ({ keys: async () => entries, delete: remove }));
    const sw = compileSW(vi.fn(), stubs.caches);
    let activation: Promise<unknown> | undefined;
    sw.handlers.get('activate')?.({ waitUntil: (promise) => { activation = promise; } });
    expect(activation).toBeDefined();
    await activation;
    expect(stubs.caches.open).toHaveBeenCalledTimes(2);
    expect(remove).toHaveBeenCalledTimes(6);
    expect(remove.mock.calls.map(([request]) => request.url)).not.toContain(entries[3].url);
  });

  it('honors no-store responses and removes an older copy', async () => {
    const stubs = makeCacheStubs();
    const remove = vi.fn(async () => true);
    stubs.caches.keys = vi.fn(async () => ['clinic-dynamic-current']);
    stubs.caches.open = vi.fn(async () => ({ delete: remove, put: stubs.put }));
    const sw = compileSW(vi.fn(async () => new Response('fresh', {
      headers: { 'Cache-Control': 'private, no-store' },
    })), stubs.caches);
    const request = { url: 'https://clinic.test/api/v1/patients', headers: new Headers() };
    const response = await sw.networkFirst(request, 'DYNAMIC_CACHE');
    expect(response.ok).toBe(true);
    expect(stubs.put).not.toHaveBeenCalled();
    expect(remove).toHaveBeenCalledWith(request, { ignoreVary: true });
  });

  it('returns a successful live response when writing the cache fails', async () => {
    const stubs = makeCacheStubs();
    stubs.put.mockRejectedValue(new Error('quota'));
    stubs.caches.match = vi.fn(async () => new Response('STALE'));
    const sw = compileSW(vi.fn(async () => new Response('LIVE')), stubs.caches);
    const response = await sw.handleRequest({
      url: 'https://clinic.test/api/v1/patients', mode: 'cors', headers: new Headers(),
    });
    expect(await response.text()).toBe('LIVE');
  });

  it('returns a successful live static response when writing the cache fails', async () => {
    const stubs = makeCacheStubs();
    stubs.put.mockRejectedValue(new Error('quota'));
    const sw = compileSW(vi.fn(async () => new Response('LIVE_ASSET')), stubs.caches);
    const response = await sw.handleRequest({
      url: 'https://clinic.test/assets/app.js', mode: 'cors', headers: new Headers(),
    });
    expect(await response.text()).toBe('LIVE_ASSET');
  });

  it('returns a live no-store response when eviction fails and refuses later stale fallback', async () => {
    const stubs = makeCacheStubs();
    stubs.caches.keys = vi.fn(async () => ['clinic-dynamic-current']);
    stubs.caches.open = vi.fn(async () => ({ delete: vi.fn(async () => { throw new Error('unavailable'); }) }));
    stubs.caches.match = vi.fn(async () => new Response('STALE'));
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(new Response('LIVE', { headers: { 'Cache-Control': 'no-store' } }))
      .mockRejectedValueOnce(new Error('offline'));
    const sw = compileSW(fetchImpl, stubs.caches);
    const request = { url: 'https://clinic.test/api/v1/patients', mode: 'cors', headers: new Headers() };
    expect(await (await sw.handleRequest(request)).text()).toBe('LIVE');
    const offline = await sw.handleRequest(request);
    expect(offline.status).toBe(503);
    expect(stubs.caches.match).not.toHaveBeenCalled();
  });

  it('finishes activation with fallback disabled if old cache cleanup fails', async () => {
    const stubs = makeCacheStubs();
    stubs.caches.keys = vi.fn(async () => ['clinic-offline-data']);
    stubs.caches.open = vi.fn(async () => { throw new Error('unavailable'); });
    stubs.caches.match = vi.fn(async () => new Response('STALE'));
    const sw = compileSW(vi.fn(async () => { throw new Error('offline'); }), stubs.caches);
    let activation: Promise<unknown> | undefined;
    sw.handlers.get('activate')?.({ waitUntil: (promise) => { activation = promise; } });
    await expect(activation).resolves.toBeUndefined();
    const offline = await sw.handleRequest({
      url: 'https://clinic.test/api/v1/patients', mode: 'cors', headers: new Headers(),
    });
    expect(offline.status).toBe(503);
    expect(stubs.caches.match).not.toHaveBeenCalled();
  });

  it.each(['resolves', 'rejects'])('honors install no-store when body cancellation %s', async (outcome) => {
    const stubs = makeCacheStubs();
    const remove = vi.fn(async () => true);
    stubs.caches.keys = vi.fn(async () => ['clinic-static-current']);
    stubs.caches.open = vi.fn(async () => ({ delete: remove, put: stubs.put }));
    const cancel = vi.fn();
    if (outcome === 'rejects') cancel.mockRejectedValue(new Error('cancellation failed'));
    const sw = compileSW(vi.fn(async (url: string) => url === '/dashboard'
      ? new Response(new ReadableStream({ cancel }), { headers: { 'Cache-Control': 'no-store' } })
      : new Response('data')), stubs.caches);
    let install: Promise<unknown> | undefined;
    sw.handlers.get('install')?.({ waitUntil: (promise) => { install = promise; } });
    await install;
    expect(cancel).toHaveBeenCalledOnce();
    expect(stubs.put.mock.calls.map(([url]) => url)).not.toContain('/dashboard');
    expect(stubs.put.mock.calls.map(([url]) => url)).toContain('/offline.html');
    expect(remove).toHaveBeenCalledWith('/dashboard', { ignoreVary: true });
  });

  it('evicts an old background sync response when the fresh response says no-store', async () => {
    const stubs = makeCacheStubs();
    const remove = vi.fn(async () => true);
    stubs.caches.keys = vi.fn(async () => ['clinic-api-current']);
    stubs.caches.open = vi.fn(async () => ({ delete: remove, put: stubs.put }));
    const sw = compileSW(vi.fn(async (url: string) => new Response('data', {
      headers: url.includes('/queue/') ? { 'Cache-Control': 'no-store' } : {},
    })), stubs.caches);
    await sw.syncClinicData();
    expect(remove).toHaveBeenCalledWith('/api/v1/queue/today', { ignoreVary: true });
    expect(stubs.put.mock.calls.map(([url]) => url)).not.toContain('/api/v1/queue/today');
    expect(stubs.put.mock.calls.map(([url]) => url)).toContain('/api/v1/mobile/notifications');
  });

  it('filters sensitive CACHE_URLS messages and no-store responses', async () => {
    const stubs = makeCacheStubs();
    const fetched: string[] = [];
    const sw = compileSW(vi.fn(async (url: string) => {
      fetched.push(url);
      return new Response('data', { headers: url.includes('private') ? { 'Cache-Control': 'no-store' } : {} });
    }), stubs.caches);
    let finished: Promise<unknown> | undefined;
    sw.handlers.get('message')?.({
      data: { type: 'CACHE_URLS', urls: [
        '/reset-password?token=SYNTHETIC_SECRET',
        '/api/v1/password-reset/validate-token',
        '/api/v1/patients', '/api/v1/patients/private',
      ] },
      waitUntil: (promise) => { finished = promise; },
    });
    await finished;
    expect(fetched).toEqual(['/api/v1/patients', '/api/v1/patients/private']);
    expect(stubs.put).toHaveBeenCalledTimes(1);
    expect(stubs.put.mock.calls[0][0]).toBe('/api/v1/patients');
  });
});
