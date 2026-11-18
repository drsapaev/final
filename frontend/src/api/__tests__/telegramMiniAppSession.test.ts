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
    const { telegramMiniAppSessions, store } = await client();
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
    await telegramMiniAppSessions.list('launch-b');
    finishRefresh({ data: pair('old-a') });
    expect(await oldRequest).toBe('replaced');
    expect(store.get()?.access_token).toBe('access-b');
  });

  it('cannot clear a replacement launch when an older logout completes', async () => {
    const { telegramMiniAppSessions, store } = await client();
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
    await telegramMiniAppSessions.list('launch-b');
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
      const { telegramMiniAppApi, telegramMiniAppSessions, store } = await client();
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
      await telegramMiniAppSessions.list('launch-b');

      if (status === 200) finishProtected({ data: { patient: 'synthetic-a' } });
      else failProtected(failure(status, 'synthetic_failure'));

      await expect(request).rejects.toMatchObject({ code: 'ERR_CANCELED', name: 'CanceledError' });
      expect(store.get()?.access_token).toBe('access-b');
    },
  );
});
