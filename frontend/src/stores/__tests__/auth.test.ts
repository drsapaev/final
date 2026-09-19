import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', () => ({
  me: vi.fn(),
  setToken: vi.fn(),
  // Phase 0 follow-up: the store registers its session-termination listener
  // in the client at module scope — stub it so registration is a no-op.
  setSessionInvalidationListener: vi.fn(),
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
  let storageOps: string[] = [];

  function primeSessionStorage(initial: Record<string, string> = {}) {
    storage = { ...initial };
    storageOps = [];
    vi.spyOn(sessionStorage, 'getItem').mockImplementation((key: string) =>
      Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null
    );
    vi.spyOn(sessionStorage, 'setItem').mockImplementation((key: string, value: string) => {
      storageOps.push(`set:${key}`);
      storage[key] = String(value);
    });
    vi.spyOn(sessionStorage, 'removeItem').mockImplementation((key: string) => {
      storageOps.push(`remove:${key}`);
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

  describe('replaceAccessOnlySession (Phase 0 PR-B review P1)', () => {
    const patientProfile = { id: 42, username: 'patient-42', role: 'Patient' };

    it('replaces a staff session with an access-only patient session (stale refresh token removed)', async () => {
      primeSessionStorage({
        auth_token: createJwt(3600),
        refresh_token: 'staff-refresh-token',
        auth_profile: JSON.stringify({ id: 1, username: 'registrar', role: 'Registrar' }),
        user: JSON.stringify({ id: 1, username: 'registrar', role: 'Registrar' }),
      });

      const auth = await import('../auth');
      const patientJwt = createJwt(600);
      auth.replaceAccessOnlySession(patientJwt, patientProfile as never);

      // The stale staff refresh token is gone — it can never be replayed on
      // /authentication/refresh under the patient session.
      expect(storage.refresh_token).toBeUndefined();
      // Access token + profile now belong to the patient principal.
      expect(storage.auth_token).toBe(patientJwt);
      expect(JSON.parse(storage.auth_profile)).toEqual(patientProfile);
      // tokenManager's `user` payload is replaced with the same principal.
      expect(JSON.parse(storage.user)).toEqual(patientProfile);
      expect(setClientTokenMock).toHaveBeenCalledWith(patientJwt);
    });

    it('clears the refresh token BEFORE installing the new principal (atomic replacement order)', async () => {
      primeSessionStorage({
        auth_token: createJwt(3600),
        refresh_token: 'staff-refresh-token',
        auth_profile: JSON.stringify({ id: 1, username: 'registrar' }),
      });

      const auth = await import('../auth');
      auth.replaceAccessOnlySession(createJwt(600), patientProfile as never);

      // Ordering contract: no window where the new patient access token and
      // the old staff refresh token coexist in storage.
      const removeRefreshIdx = storageOps.indexOf('remove:refresh_token');
      const setTokenIdx = storageOps.indexOf('set:auth_token');
      const setProfileIdx = storageOps.indexOf('set:auth_profile');
      expect(removeRefreshIdx).toBeGreaterThanOrEqual(0);
      expect(setTokenIdx).toBeGreaterThan(removeRefreshIdx);
      expect(setProfileIdx).toBeGreaterThan(setTokenIdx);
    });

    it('is idempotent for an access-only session (no refresh token present)', async () => {
      primeSessionStorage({
        auth_token: createJwt(3600),
        auth_profile: JSON.stringify({ id: 42, username: 'patient-42', role: 'Patient' }),
      });

      const auth = await import('../auth');
      const patientJwt = createJwt(1200);
      expect(() => auth.replaceAccessOnlySession(patientJwt, patientProfile as never)).not.toThrow();

      expect(storage.refresh_token).toBeUndefined();
      expect(storage.auth_token).toBe(patientJwt);
      expect(JSON.parse(storage.auth_profile)).toEqual(patientProfile);
    });
  });

  describe('expired principal kind marker (Phase 0 follow-up, Codex P1 round 3)', () => {
    it('remembers an expired PATIENT principal and resets on the next login', async () => {
      primeSessionStorage({
        auth_token: 'jwt',
        auth_profile: JSON.stringify({ id: 9, username: 'patient-9', role: 'Patient' }),
      });

      const auth = await import('../auth');
      auth.clearToken();
      expect(auth.getExpiredPrincipalWasPatient()).toBe(true);

      // A freshly installed session resets the marker.
      auth.setToken('fresh-jwt');
      expect(auth.getExpiredPrincipalWasPatient()).toBe(false);
    });

    it('does not flag staff principals on clearToken', async () => {
      primeSessionStorage({
        auth_token: 'jwt',
        auth_profile: JSON.stringify({ id: 2, username: 'registrar', role: 'Registrar' }),
      });

      const auth = await import('../auth');
      auth.clearToken();
      expect(auth.getExpiredPrincipalWasPatient()).toBe(false);
    });

    it('flags nothing when the cleared session had no profile', async () => {
      primeSessionStorage({ auth_token: 'jwt' });

      const auth = await import('../auth');
      auth.clearToken();
      expect(auth.getExpiredPrincipalWasPatient()).toBe(false);
    });
  });
});
