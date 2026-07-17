// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client.ts', () => ({
  me: vi.fn(),
  setToken: vi.fn(),
}));

import { me, setToken as setClientToken } from '../../api/client.ts';

function createJwt(expSecondsFromNow) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({
    sub: '1',
    exp: Math.floor(Date.now() / 1000) + expSecondsFromNow,
  }));
  return `${header}.${payload}.signature`;
}

describe('auth store', () => {
  let storage;

  function primeSessionStorage(initial = {}) {
    storage = { ...initial };
    sessionStorage.getItem.mockImplementation((key) =>
      Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null
    );
    sessionStorage.setItem.mockImplementation((key, value) => {
      storage[key] = String(value);
    });
    sessionStorage.removeItem.mockImplementation((key) => {
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
    me.mockRejectedValueOnce({ response: { status: 401 } });

    const auth = await import('../auth.ts');
    const profile = await auth.getProfile(true);

    expect(profile).toBeNull();
    expect(storage.auth_token).toBeUndefined();
    expect(storage.auth_profile).toBeUndefined();
    expect(setClientToken).toHaveBeenCalledWith(null);
  });

  it('clears expired tokens before protected routes hit the API', async () => {
    primeSessionStorage({
      auth_token: createJwt(-3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });

    const auth = await import('../auth.ts');
    const state = await auth.validateSession(true);

    expect(me).not.toHaveBeenCalled();
    expect(state).toEqual({ token: null, profile: null });
    expect(storage.auth_token).toBeUndefined();
    expect(storage.auth_profile).toBeUndefined();
  });

  it('reuses a recent validated session instead of calling /auth/me again', async () => {
    primeSessionStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    me.mockResolvedValue({ id: 1, username: 'registrar' });

    const auth = await import('../auth.ts');
    const firstState = await auth.validateSession(true);
    const secondState = await auth.validateSession();

    expect(firstState).toEqual({
      token: storage.auth_token,
      profile: { id: 1, username: 'registrar' },
    });
    expect(secondState).toEqual(firstState);
    expect(me).toHaveBeenCalledTimes(1);
  });

  it('keeps cached auth state when /auth/me is rate limited', async () => {
    primeSessionStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    me.mockRejectedValueOnce({ response: { status: 429 } });

    const auth = await import('../auth.ts');
    const state = await auth.validateSession(true);

    expect(state).toEqual({
      token: storage.auth_token,
      profile: { id: 1, username: 'registrar' },
    });
    expect(storage.auth_token).toBeDefined();
    expect(storage.auth_profile).toBeDefined();
  });
});
