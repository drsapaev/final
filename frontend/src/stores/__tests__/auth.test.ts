import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', () => ({
  me: vi.fn(),
  setToken: vi.fn(),
}));

import { me, setToken as setClientToken } from '../../api/client';

// Cast me and setClientToken through unknown so we can call vitest
// mock methods (mockResolvedValue / mockRejectedValueOnce / etc.) —
// the real me() returns Promise<UserProfile>, not a Mock.
const meMock = me as unknown as ReturnType<typeof vi.fn>;
const setClientTokenMock = setClientToken as unknown as ReturnType<typeof vi.fn>;

function createJwt(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({
    sub: '1',
    exp: Math.floor(Date.now() / 1000) + expSecondsFromNow,
  }));
  return `${header}.${payload}.signature`;
}

describe('auth store', () => {
  let storage: Record<string, string>;

  function primeSessionStorage(initial: Record<string, string> = {}) {
    storage = { ...initial };
    vi.spyOn(sessionStorage, 'getItem').mockImplementation((key: string) =>
      Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null
    );
    vi.spyOn(sessionStorage, 'setItem').mockImplementation((key: string, value: string) => {
      storage[key] = String(value);
    });
    vi.spyOn(sessionStorage, 'removeItem').mockImplementation((key: string) => {
      delete storage[key];
    });
  }

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    primeSessionStorage();
  });

  it('clears auth state when backend returns 401 during profile validation', async () => {
    primeSessionStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    meMock.mockRejectedValueOnce({ response: { status: 401 } });

    const auth = await import('../auth');
    const profile = await auth.getProfile(true);

    expect(profile).toBeNull();
    expect(storage.auth_token).toBeUndefined();
    expect(storage.auth_profile).toBeUndefined();
    expect(setClientTokenMock).toHaveBeenCalledWith(null);
  });

  it('clears expired tokens before protected routes hit the API', async () => {
    primeSessionStorage({
      auth_token: createJwt(-3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });

    const auth = await import('../auth');
    const state = await auth.validateSession(true);

    expect(meMock).not.toHaveBeenCalled();
    expect(state).toEqual({ token: null, profile: null });
    expect(storage.auth_token).toBeUndefined();
    expect(storage.auth_profile).toBeUndefined();
  });

  it('reuses a recent validated session instead of calling /auth/me again', async () => {
    primeSessionStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    meMock.mockResolvedValue({ id: 1, username: 'registrar' });

    const auth = await import('../auth');
    const firstState = await auth.validateSession(true);
    const secondState = await auth.validateSession();

    expect(firstState).toEqual({
      token: storage.auth_token,
      profile: { id: 1, username: 'registrar' },
    });
    expect(secondState).toEqual(firstState);
    expect(meMock).toHaveBeenCalledTimes(1);
  });

  it('keeps cached auth state when /auth/me is rate limited', async () => {
    primeSessionStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    meMock.mockRejectedValueOnce({ response: { status: 429 } });

    const auth = await import('../auth');
    const state = await auth.validateSession(true);

    expect(state).toEqual({
      token: storage.auth_token,
      profile: { id: 1, username: 'registrar' },
    });
    expect(storage.auth_token).toBeDefined();
    expect(storage.auth_profile).toBeDefined();
  });
});
