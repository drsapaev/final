import { webcrypto } from 'node:crypto';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), create: vi.fn() }));
vi.mock('axios', () => ({
  default: {
    create: mocks.create,
    isAxiosError: (error: { isAxiosError?: boolean }) => Boolean(error?.isAxiosError),
    CanceledError: class MockCanceledError extends Error {
      code = 'ERR_CANCELED';
      __CANCEL__ = true;
      isAxiosError = true;
      constructor(message: string) {
        super(message);
        this.name = 'CanceledError';
      }
    },
  },
}));
vi.mock('../runtime', () => ({ getApiBaseUrl: () => 'https://api.example.test/api/v1' }));

const pair = (suffix = '1') => ({
  access_token: `access-${suffix}`, refresh_token: `refresh-${suffix}`,
  expires_in: 900, token_type: 'bearer' as const,
});
const failure = (status: number, reason: string, headers = {}) => Object.assign(new Error('request failed'), {
  isAxiosError: true, response: { status, data: { detail: { reason } }, headers },
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolveValue, rejectValue) => {
    resolve = resolveValue;
    reject = rejectValue;
  });
  return { promise, resolve, reject };
}

const digest = (byte: number) => new Uint8Array(32).fill(byte).buffer;

async function client() {
  const api = await import('../telegramMiniAppSession');
  const { miniAppTokenManager } = await import('../../utils/tokenManager');
  return { ...api, store: miniAppTokenManager };
}

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  sessionStorage.clear();
  vi.stubGlobal('crypto', webcrypto);
  mocks.create.mockReturnValue({ get: mocks.get, post: mocks.post });
  mocks.get.mockResolvedValue({ data: { csrf_token: 'synthetic-csrf' } });
  mocks.post.mockImplementation((url: string) => Promise.resolve({
    data: url.endsWith('/auth/exchange') || url.endsWith('/auth/refresh')
      ? pair() : { sessions: [], total: 0 },
  }));
});

describe('isolated Telegram patient session client', () => {
  it('keeps same-launch reads alive while they share an unfinished exchange', async () => {
    const pendingExchange = deferred<{ data: ReturnType<typeof pair> }>();
    vi.stubGlobal('crypto', { subtle: { digest: vi.fn().mockResolvedValue(digest(1)) } });
    mocks.post.mockImplementation((url: string) => url.endsWith('/auth/exchange')
      ? pendingExchange.promise : Promise.resolve({ data: { sessions: [], total: 0 } }));
    const { telegramMiniAppSessions } = await client();
    const first = telegramMiniAppSessions.list('launch-a');
    await vi.waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
    const second = telegramMiniAppSessions.list('launch-a');
    const settled = Promise.allSettled([first, second]);
    await vi.waitFor(() => expect(crypto.subtle.digest).toHaveBeenCalledTimes(2));
    await new Promise((resolve) => setTimeout(resolve, 0));
    pendingExchange.resolve({ data: pair('a') });
    expect((await settled).every((result) => result.status === 'fulfilled')).toBe(true);
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/auth/exchange'))).toHaveLength(1);
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/sessions/list'))).toHaveLength(2);
  });

  it('does not let an older delayed digest replace a newer patient launch', async () => {
    const pendingDigest = deferred<ArrayBuffer>();
    vi.stubGlobal('crypto', { subtle: { digest: vi.fn((_algorithm: unknown, bytes: Uint8Array) => (
      new TextDecoder().decode(bytes) === 'launch-a' ? pendingDigest.promise : Promise.resolve(digest(2))
    )) } });
    mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => Promise.resolve({
      data: url.endsWith('/auth/exchange') ? pair(body?.init_data === 'launch-b' ? 'b' : 'a') : {},
    }));
    const { telegramMiniAppApi, store } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    pendingDigest.resolve(digest(1));
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(store.get()?.access_token).toBe('access-b');
    expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/cabinet/summary'))).toBe(false);
  });

  it('cancels an old patient response after switching to a scoped entry link', async () => {
    const protectedResponse = deferred<{ data: object }>();
    mocks.post.mockImplementation((url: string) => {
      if (url.endsWith('/cabinet/summary')) return protectedResponse.promise;
      return Promise.resolve({ data: url.endsWith('/auth/exchange') ? pair('a') : {} });
    });
    const { telegramMiniAppApi, store } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/cabinet/summary'))).toBe(true));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-b' });
    protectedResponse.resolve({ data: { patient: 'synthetic-a' } });
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(store.get()).toBeNull();
  });

  it('cancels an old scoped-entry response after switching to a patient launch', async () => {
    const entryResponse = deferred<{ data: object }>();
    mocks.post.mockImplementation((url: string, body?: { entryToken?: string }) => {
      if (url.endsWith('/patient/manifest') && body?.entryToken === 'synthetic-entry-a') return entryResponse.promise;
      return Promise.resolve({ data: url.endsWith('/auth/exchange') ? pair('b') : {} });
    });
    const { telegramMiniAppApi, store } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/patient/manifest'))).toBe(true));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    entryResponse.resolve({ data: { patient: 'synthetic-a' } });
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(store.get()?.access_token).toBe('access-b');
  });

  it('keeps an earlier response canceled when its follow-on request is stale', async () => {
    const oldResponse = deferred<{ data: object }>();
    let exchanges = 0;
    mocks.post.mockImplementation((url: string) => {
      if (url.endsWith('/cabinet/summary')) return oldResponse.promise;
      if (url.endsWith('/auth/exchange')) {
        exchanges += 1;
        return exchanges === 1 ? Promise.resolve({ data: pair('a') }) : Promise.reject(failure(401, 'init_data_replayed'));
      }
      return Promise.resolve({ data: {} });
    });
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/cabinet/summary'))).toBe(true));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-b' });
    await expect(telegramMiniAppSessions.list('launch-a')).rejects.toMatchObject({ code: 'ERR_CANCELED' });
    oldResponse.resolve({ data: { patient: 'synthetic-a' } });
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(store.get()).toBeNull();
    expect(exchanges).toBe(1);
    await expect(telegramMiniAppApi.post('/telegram/mini-app/onboarding/requests', {
      entryToken: 'synthetic-entry-b',
    })).resolves.toBeDefined();
  });

  it('does not send a stale onboarding fallback after another launch takes over', async () => {
    const oldExchange = deferred<{ data: ReturnType<typeof pair> }>();
    mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => {
      if (url.endsWith('/auth/exchange') && body?.init_data === 'launch-a') return oldExchange.promise;
      return Promise.resolve({ data: url.endsWith('/auth/exchange') ? pair('b') : {} });
    });
    const { telegramMiniAppApi, store } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post.mock.calls.some(([url, body]) => (
      url.endsWith('/auth/exchange') && body.init_data === 'launch-a'
    ))).toBe(true));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    oldExchange.reject(failure(403, 'patient_scope_required'));
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/patient/manifest'))).toHaveLength(1);
    expect(store.get()?.access_token).toBe('access-b');
  });

  it('does not dispatch an old exchange after CSRF bootstrap and a launch switch', async () => {
    const csrf = deferred<{ data: { csrf_token: string } }>();
    mocks.get.mockReturnValue(csrf.promise);
    mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => Promise.resolve({
      data: url.endsWith('/auth/exchange') ? pair(body?.init_data === 'launch-b' ? 'b' : 'a') : {},
    }));
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    const oldRequest = telegramMiniAppSessions.list('launch-a')
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1));
    const newRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    csrf.resolve({ data: { csrf_token: 'synthetic-csrf' } });
    await newRequest;
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(mocks.post.mock.calls.some(([url, body]) => url.endsWith('/auth/exchange') && body.init_data === 'launch-a')).toBe(false);
    expect(store.get()?.access_token).toBe('access-b');
  });

  it('does not retry an old patient action after CSRF recovery and a launch switch', async () => {
    const recovery = deferred<{ data: { csrf_token: string } }>();
    mocks.get.mockResolvedValueOnce({ data: { csrf_token: 'synthetic-csrf' } }).mockReturnValueOnce(recovery.promise);
    mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => {
      if (url.endsWith('/auth/exchange')) return Promise.resolve({ data: pair(body?.init_data === 'launch-b' ? 'b' : 'a') });
      if (url.endsWith('/appointments')) return Promise.reject(failure(403, '', { 'x-csrf-status': 'rejected' }));
      return Promise.resolve({ data: {} });
    });
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/appointments', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2));
    const newRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    recovery.resolve({ data: { csrf_token: 'synthetic-csrf-next' } });
    await newRequest;
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/appointments'))).toHaveLength(1);
    expect(store.get()?.access_token).toBe('access-b');
  });

  it.each([403, 500])('cancels a stale scoped-entry HTTP %i error after a launch switch', async (status) => {
    const entryResponse = deferred<{ data: object }>();
    mocks.post.mockImplementation((url: string, body?: { entryToken?: string }) => {
      if (url.endsWith('/patient/manifest') && body?.entryToken === 'synthetic-entry-a') return entryResponse.promise;
      return Promise.resolve({ data: url.endsWith('/auth/exchange') ? pair('b') : {} });
    });
    const { telegramMiniAppApi, store } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    entryResponse.reject(failure(status, 'synthetic_failure'));
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(store.get()?.access_token).toBe('access-b');
  });

  it('clears a resumed Mini App session when a scoped entry opens, without clearing staff login', async () => {
    sessionStorage.setItem('auth_token', 'staff-access');
    const initial = await client();
    await initial.telegramMiniAppSessions.list('launch-a');
    expect(sessionStorage.getItem('telegram_mini_app_session')).not.toContain('launch-a');
    vi.resetModules();
    const resumed = await client();
    await resumed.telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-b' });
    expect(resumed.store.get()).toBeNull();
    expect(sessionStorage.getItem('telegram_mini_app_session')).toBeNull();
    expect(sessionStorage.getItem('auth_token')).toBe('staff-access');
  });

  it('does not dispatch a stale logout after a newer launch supersedes its digest', async () => {
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    const pendingDigest = deferred<ArrayBuffer>();
    vi.stubGlobal('crypto', { subtle: { digest: vi.fn((_algorithm: unknown, bytes: Uint8Array) => (
      new TextDecoder().decode(bytes) === 'launch-a' ? pendingDigest.promise : Promise.resolve(digest(2))
    )) } });
    mocks.post.mockImplementation((url: string) => Promise.resolve({
      data: url.endsWith('/auth/exchange') ? pair('b') : {},
    }));
    const oldLogout = telegramMiniAppSessions.logout('launch-a')
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    pendingDigest.resolve(digest(1));
    expect(await oldLogout).toBe('ERR_CANCELED');
    expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/auth/logout'))).toBe(false);
    expect(store.get()?.access_token).toBe('access-b');
  });

  it.each(['logout', 'revoke', 'revokeOthers'] as const)(
    'does not let a stale %s action replace the current patient session',
    async (action) => {
      mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => Promise.resolve({
        data: url.endsWith('/auth/exchange') ? pair(body?.init_data === 'launch-b' ? 'b' : 'a') : {},
      }));
      const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
      await telegramMiniAppSessions.list('launch-a');
      await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
      const sent = mocks.post.mock.calls.length;
      const staleAction = action === 'logout' ? telegramMiniAppSessions.logout('launch-a')
        : action === 'revoke' ? telegramMiniAppSessions.revoke('synthetic-device', 'launch-a')
          : telegramMiniAppSessions.revokeOthers('launch-a');
      await expect(staleAction).rejects.toMatchObject({ code: 'ERR_CANCELED' });
      expect(mocks.post).toHaveBeenCalledTimes(sent);
      expect(store.get()?.access_token).toBe('access-b');
    },
  );

  it.each(['list', 'protected request'] as const)(
    'does not let an old %s replace a newer patient launch',
    async (operation) => {
      mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => Promise.resolve({
        data: url.endsWith('/auth/exchange') ? pair(body?.init_data === 'launch-b' ? 'b' : 'a') : {},
      }));
      const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
      await telegramMiniAppSessions.list('launch-a');
      await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
      const sent = mocks.post.mock.calls.length;

      const stale = operation === 'list' ? telegramMiniAppSessions.list('launch-a')
        : telegramMiniAppApi.post('/telegram/mini-app/appointments/preview', { initData: 'launch-a' });

      await expect(stale).rejects.toMatchObject({ code: 'ERR_CANCELED' });
      expect(mocks.post).toHaveBeenCalledTimes(sent);
      expect(store.get()?.access_token).toBe('access-b');
    },
  );

  it('does not let an old scoped request replace a newer scoped launch', async () => {
    const { telegramMiniAppApi } = await client();
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-a' });
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-b' });
    const sent = mocks.post.mock.calls.length;

    await expect(telegramMiniAppApi.post('/telegram/mini-app/onboarding/requests', {
      entryToken: 'synthetic-entry-a',
    })).rejects.toMatchObject({ code: 'ERR_CANCELED' });
    expect(mocks.post).toHaveBeenCalledTimes(sent);
    await expect(telegramMiniAppApi.post('/telegram/mini-app/onboarding/requests', {
      entryToken: 'synthetic-entry-b',
    })).resolves.toBeDefined();
  });

  it('uses the manifest launch for subsequent patient and device requests', async () => {
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();

    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    await telegramMiniAppSessions.list('launch-b');
    await telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', { initData: 'launch-b' });

    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/auth/exchange'))).toHaveLength(1);
    expect(store.get()?.access_token).toBe('access-1');
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/sessions/list'))).toHaveLength(1);
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/cabinet/summary'))).toHaveLength(1);
  });

  it('sends confirmed device revocations for the current patient session', async () => {
    sessionStorage.setItem('auth_token', 'staff-access');
    const { telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    await telegramMiniAppSessions.revoke('synthetic/device', 'launch-a');
    expect(mocks.post).toHaveBeenLastCalledWith(
      '/telegram/mini-app/sessions/synthetic%2Fdevice/revoke', {},
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer access-1' }) }),
    );
    await telegramMiniAppSessions.revokeOthers('launch-a');
    expect(mocks.post).toHaveBeenLastCalledWith(
      '/telegram/mini-app/sessions/revoke-all', {},
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer access-1' }) }),
    );
    expect(store.get()?.access_token).toBe('access-1');
    expect(sessionStorage.getItem('auth_token')).toBe('staff-access');
  });

  it('allows a current device action after reloading the tab-scoped session', async () => {
    const initial = await client();
    await initial.telegramMiniAppSessions.list('launch-a');
    vi.resetModules();
    mocks.post.mockClear();
    const resumed = await client();
    await resumed.telegramMiniAppSessions.revokeOthers('launch-a');
    expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/auth/exchange'))).toBe(false);
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/sessions/revoke-all'))).toHaveLength(1);
  });

  it('cancels an older pending digest after logout without reopening the session', async () => {
    vi.stubGlobal('crypto', { subtle: { digest: vi.fn().mockResolvedValue(digest(1)) } });
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    const pendingDigest = deferred<ArrayBuffer>();
    vi.stubGlobal('crypto', { subtle: { digest: vi.fn()
      .mockReturnValueOnce(pendingDigest.promise)
      .mockResolvedValue(digest(1)) } });
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await telegramMiniAppSessions.logout('launch-a');
    pendingDigest.resolve(digest(1));
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/cabinet/summary'))).toBe(false);
    expect(store.get()).toBeNull();
  });

  it('does not send a superseded scoped entry after CSRF bootstrap', async () => {
    const csrf = deferred<{ data: { csrf_token: string } }>();
    mocks.get.mockReturnValue(csrf.promise);
    const { telegramMiniAppApi } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1));
    const next = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-b' });
    csrf.resolve({ data: { csrf_token: 'synthetic-csrf' } });
    await next;
    expect(await oldRequest).toBe('ERR_CANCELED');
    expect(mocks.post.mock.calls.some(([, body]) => body.entryToken === 'synthetic-entry-a')).toBe(false);
    expect(mocks.post.mock.calls.filter(([, body]) => body.entryToken === 'synthetic-entry-b')).toHaveLength(1);
  });

  it('cancels an old response as soon as a new launch starts hashing', async () => {
    const newDigest = deferred<ArrayBuffer>();
    const oldResponse = deferred<{ data: object }>();
    vi.stubGlobal('crypto', { subtle: { digest: vi.fn((_algorithm: unknown, bytes: Uint8Array) => (
      new TextDecoder().decode(bytes) === 'launch-b' ? newDigest.promise : Promise.resolve(digest(1))
    )) } });
    mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => {
      if (url.endsWith('/cabinet/summary')) return oldResponse.promise;
      return Promise.resolve({ data: url.endsWith('/auth/exchange') ? pair(body?.init_data === 'launch-b' ? 'b' : 'a') : {} });
    });
    const { telegramMiniAppApi, store } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/cabinet/summary'))).toBe(true));
    const next = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    oldResponse.resolve({ data: { patient: 'synthetic-a' } });
    expect(await oldRequest).toBe('ERR_CANCELED');
    newDigest.resolve(digest(2));
    await next;
    expect(store.get()?.access_token).toBe('access-b');
  });

  it('cancels a scoped-entry response after another scoped entry takes over', async () => {
    const firstResponse = deferred<{ data: object }>();
    mocks.post.mockImplementation((_url: string, body?: { entryToken?: string }) => (
      body?.entryToken === 'synthetic-entry-a' ? firstResponse.promise : Promise.resolve({ data: {} })
    ));
    const { telegramMiniAppApi } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { entryToken: 'synthetic-entry-b' });
    firstResponse.resolve({ data: { patient: 'synthetic-a' } });
    expect(await oldRequest).toBe('ERR_CANCELED');
  });

  it('cancels a stale onboarding response after another launch starts', async () => {
    const onboardingResponse = deferred<{ data: object }>();
    mocks.post.mockImplementation((url: string) => {
      if (url.includes('/onboarding/')) return onboardingResponse.promise;
      return Promise.resolve({ data: url.endsWith('/auth/exchange') ? pair('b') : {} });
    });
    const { telegramMiniAppApi } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/onboarding/requests', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post.mock.calls.some(([url]) => url.includes('/onboarding/'))).toBe(true));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    onboardingResponse.resolve({ data: { synthetic: true } });
    expect(await oldRequest).toBe('ERR_CANCELED');
  });

  it('discards an already-dispatched fallback response after a launch switch', async () => {
    const fallbackResponse = deferred<{ data: object }>();
    mocks.post.mockImplementation((url: string, body?: { init_data?: string; initData?: string }) => {
      if (url.endsWith('/auth/exchange') && body?.init_data === 'launch-a') return Promise.reject(failure(403, 'patient_scope_required'));
      if (url.endsWith('/patient/manifest') && body?.initData === 'launch-a') return fallbackResponse.promise;
      return Promise.resolve({ data: url.endsWith('/auth/exchange') ? pair('b') : {} });
    });
    const { telegramMiniAppApi } = await client();
    const oldRequest = telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-a' })
      .then(() => 'unexpected-success', (error: { code?: string }) => error.code);
    await vi.waitFor(() => expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/patient/manifest'))).toBe(true));
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    fallbackResponse.resolve({ data: { scope: { type: 'onboarding' } } });
    expect(await oldRequest).toBe('ERR_CANCELED');
  });
  it('exchanges initData once for concurrent reads and never borrows staff credentials', async () => {
    sessionStorage.setItem('auth_token', 'staff-access');
    sessionStorage.setItem('refresh_token', 'staff-refresh');
    const { telegramMiniAppSessions } = await client();
    await Promise.all([telegramMiniAppSessions.list('launch-a'), telegramMiniAppSessions.list('launch-a')]);
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/auth/exchange'))).toHaveLength(1);
    const requests = mocks.post.mock.calls.filter(([url]) => url.endsWith('/sessions/list'));
    expect(requests).toHaveLength(2);
    for (const [, body, config] of requests) {
      expect(body).toEqual({});
      expect(config.headers.Authorization).toBe('Bearer access-1');
      expect(config.headers['X-CSRF-Token']).toBe('synthetic-csrf');
    }
    expect(sessionStorage.getItem('auth_token')).toBe('staff-access');
    expect(sessionStorage.getItem('refresh_token')).toBe('staff-refresh');
  });

  it('removes initData from all subsequent protected request bodies', async () => {
    const { telegramMiniAppApi } = await client();
    await telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', {
      initData: 'launch-a', section: 'cabinet',
    });
    expect(mocks.post).toHaveBeenLastCalledWith(
      '/telegram/mini-app/cabinet/summary', { section: 'cabinet' },
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer access-1' }) }),
    );
  });

  it('rotates refresh once when concurrent requests find an expiring access token', async () => {
    const { telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    store.set({ ...store.get()!, expires_at: 0 });
    mocks.post.mockImplementation((url: string) => Promise.resolve({
      data: url.endsWith('/auth/refresh') ? pair('2') : { sessions: [], total: 0 },
    }));
    await Promise.all([telegramMiniAppSessions.list('launch-a'), telegramMiniAppSessions.list('launch-a')]);
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(1);
    expect(store.get()?.refresh_token).toBe('refresh-2');
    expect(mocks.post.mock.calls.at(-1)?.[2].headers.Authorization).toBe('Bearer access-2');
  });

  it('resumes a tab session after module reload without replaying initData', async () => {
    const first = await client();
    await first.telegramMiniAppSessions.list('launch-a');
    vi.resetModules();
    mocks.post.mockClear();
    const second = await client();
    await second.telegramMiniAppSessions.list('launch-a');
    expect(mocks.post.mock.calls.some(([url]) => url.endsWith('/auth/exchange'))).toBe(false);
  });

  it('permits restricted onboarding fallback only for an unlinked manifest', async () => {
    const { telegramMiniAppApi } = await client();
    mocks.post.mockImplementation((url: string) => url.endsWith('/auth/exchange')
      ? Promise.reject(failure(403, 'patient_scope_required'))
      : Promise.resolve({ data: { scope: { type: 'onboarding' } } }));
    const result = await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-a' });
    expect(result.data.scope.type).toBe('onboarding');
    expect(mocks.post.mock.calls.at(-1)?.[1]).toEqual({ initData: 'launch-a' });
    await expect(telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', {
      initData: 'launch-a',
    })).rejects.toMatchObject({ response: { status: 403 } });
  });

  it('never falls back to initData after revocation and preserves staff state', async () => {
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    sessionStorage.setItem('auth_token', 'staff-access');
    await telegramMiniAppSessions.list('launch-a');
    mocks.post.mockRejectedValue(failure(401, 'session_invalid'));
    await expect(telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', {
      initData: 'launch-a',
    })).rejects.toBeDefined();
    expect(store.get()).toBeNull();
    const count = mocks.post.mock.calls.length;
    await expect(telegramMiniAppSessions.list('launch-a')).rejects.toBeDefined();
    expect(mocks.post.mock.calls).toHaveLength(count);
    expect(sessionStorage.getItem('auth_token')).toBe('staff-access');
  });

  it('does one CSRF recovery without calling refresh or losing the principal', async () => {
    const { telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    mocks.post.mockRejectedValueOnce(failure(403, '', { 'x-csrf-status': 'rejected' }))
      .mockResolvedValueOnce({ data: { sessions: [], total: 0 } });
    await telegramMiniAppSessions.list('launch-a');
    expect(mocks.get).toHaveBeenCalledTimes(2);
    expect(mocks.post.mock.calls.filter(([url]) => url.endsWith('/auth/refresh'))).toHaveLength(0);
    expect(store.get()?.access_token).toBe('access-1');
  });

  it('logout clears only the Mini App namespace and prevents automatic reentry', async () => {
    const { telegramMiniAppSessions, store } = await client();
    sessionStorage.setItem('refresh_token', 'staff-refresh');
    await telegramMiniAppSessions.list('launch-a');
    await telegramMiniAppSessions.logout('launch-a');
    expect(store.get()).toBeNull();
    expect(sessionStorage.getItem('refresh_token')).toBe('staff-refresh');
    await expect(telegramMiniAppSessions.list('launch-a')).rejects.toBeDefined();
  });

  it('keeps entry-token requests scoped and free of a staff bearer', async () => {
    const { telegramMiniAppApi } = await client();
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', {
      entryToken: 'synthetic-cabinet-token', section: 'cabinet',
    });
    expect(mocks.post.mock.calls).toHaveLength(1);
    expect(mocks.post.mock.calls[0][2].headers.Authorization).toBeUndefined();
    expect(mocks.post.mock.calls[0][1].entryToken).toBe('synthetic-cabinet-token');
  });

  it('cannot overwrite a replacement launch with a late refresh response', async () => {
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    store.set({ ...store.get()!, expires_at: 0 });
    let finishRefresh!: (response: { data: ReturnType<typeof pair> }) => void;
    mocks.post.mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) return new Promise((resolve) => { finishRefresh = resolve; });
      return Promise.resolve({
        data: url.endsWith('/auth/exchange') ? pair('b') : { sessions: [], total: 0 },
      });
    });
    const oldRequest = telegramMiniAppSessions.list('launch-a').then(
      () => 'unexpected-success', () => 'replaced',
    );
    await vi.waitFor(() => expect(finishRefresh).toBeDefined());
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    finishRefresh({ data: pair('old-a') });
    expect(await oldRequest).toBe('replaced');
    expect(store.get()?.access_token).toBe('access-b');
  });

  it('cannot clear a replacement launch when an older logout completes', async () => {
    const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
    await telegramMiniAppSessions.list('launch-a');
    let finishLogout!: (response: { data: object }) => void;
    mocks.post.mockImplementation((url: string) => {
      if (url.endsWith('/auth/logout')) return new Promise((resolve) => { finishLogout = resolve; });
      return Promise.resolve({
        data: url.endsWith('/auth/exchange') ? pair('b') : { sessions: [], total: 0 },
      });
    });
    const logout = telegramMiniAppSessions.logout('launch-a');
    await vi.waitFor(() => expect(finishLogout).toBeDefined());
    await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });
    finishLogout({ data: {} });
    await expect(logout).rejects.toMatchObject({ code: 'ERR_CANCELED', name: 'CanceledError' });
    expect(store.get()?.access_token).toBe('access-b');
  });

  it.each([200, 403, 500])(
    'cancels a late HTTP %i protected response after logout',
    async (status) => {
      const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
      let finishProtected!: (response: { data: object }) => void;
      let failProtected!: (error: unknown) => void;
      mocks.post.mockImplementation((url: string) => {
        if (url.endsWith('/telegram/mini-app/cabinet/summary')) {
          return new Promise((resolve, reject) => {
            finishProtected = resolve;
            failProtected = reject;
          });
        }
        if (url.endsWith('/auth/exchange')) return Promise.resolve({ data: pair() });
        return Promise.resolve({ data: {} });
      });

      const request = telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', {
        initData: 'launch-a',
      });
      await vi.waitFor(() => expect(finishProtected).toBeDefined());
      await telegramMiniAppSessions.logout('launch-a');

      if (status === 200) finishProtected({ data: { patient: 'synthetic-a' } });
      else failProtected(failure(status, 'synthetic_failure'));

      await expect(request).rejects.toMatchObject({ code: 'ERR_CANCELED', name: 'CanceledError' });
      expect(store.get()).toBeNull();
    },
  );

  it.each([200, 403, 500])(
    'cancels a late HTTP %i protected response after switching patients',
    async (status) => {
      const { telegramMiniAppApi, store } = await client();
      let finishProtected!: (response: { data: object }) => void;
      let failProtected!: (error: unknown) => void;
      mocks.post.mockImplementation((url: string, body?: { init_data?: string }) => {
        if (url.endsWith('/telegram/mini-app/cabinet/summary')) {
          return new Promise((resolve, reject) => {
            finishProtected = resolve;
            failProtected = reject;
          });
        }
        return Promise.resolve({
          data: url.endsWith('/auth/exchange') ? pair(body?.init_data === 'launch-b' ? 'b' : 'a') : {},
        });
      });

      const request = telegramMiniAppApi.post('/telegram/mini-app/cabinet/summary', {
        initData: 'launch-a',
      });
      await vi.waitFor(() => expect(finishProtected).toBeDefined());
      await telegramMiniAppApi.post('/telegram/mini-app/patient/manifest', { initData: 'launch-b' });

      if (status === 200) finishProtected({ data: { patient: 'synthetic-a' } });
      else failProtected(failure(status, 'synthetic_failure'));

      await expect(request).rejects.toMatchObject({ code: 'ERR_CANCELED', name: 'CanceledError' });
      expect(store.get()?.access_token).toBe('access-b');
    },
  );
});
