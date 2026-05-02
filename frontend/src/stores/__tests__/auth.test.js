import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client.js', () => ({
  me: vi.fn(),
  setToken: vi.fn(),
}));

import { me, setToken as setClientToken } from '../../api/client.js';

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

  function primeLocalStorage(initial = {}) {
    storage = { ...initial };
    localStorage.getItem.mockImplementation((key) =>
      Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null
    );
    localStorage.setItem.mockImplementation((key, value) => {
      storage[key] = String(value);
    });
    localStorage.removeItem.mockImplementation((key) => {
      delete storage[key];
    });
  }

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    primeLocalStorage();
  });

  it('clears auth state when backend returns 401 during profile validation', async () => {
    primeLocalStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    me.mockRejectedValueOnce({ response: { status: 401 } });

    const auth = await import('../auth.js');
    const profile = await auth.getProfile(true);

    expect(profile).toBeNull();
    expect(storage.auth_token).toBeUndefined();
    expect(storage.auth_profile).toBeUndefined();
    expect(setClientToken).toHaveBeenCalledWith(null);
  });

  it('clears expired tokens before protected routes hit the API', async () => {
    primeLocalStorage({
      auth_token: createJwt(-3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });

    const auth = await import('../auth.js');
    const state = await auth.validateSession(true);

    expect(me).not.toHaveBeenCalled();
    expect(state).toEqual({ token: null, profile: null });
    expect(storage.auth_token).toBeUndefined();
    expect(storage.auth_profile).toBeUndefined();
  });

  it('reuses a recent validated session instead of calling /auth/me again', async () => {
    primeLocalStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    me.mockResolvedValue({ id: 1, username: 'registrar' });

    const auth = await import('../auth.js');
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
    primeLocalStorage({
      auth_token: createJwt(3600),
      auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
    });
    me.mockRejectedValueOnce({ response: { status: 429 } });

    const auth = await import('../auth.js');
    const state = await auth.validateSession(true);

    expect(state).toEqual({
      token: storage.auth_token,
      profile: { id: 1, username: 'registrar' },
    });
    expect(storage.auth_token).toBeDefined();
    expect(storage.auth_profile).toBeDefined();
  });
});
