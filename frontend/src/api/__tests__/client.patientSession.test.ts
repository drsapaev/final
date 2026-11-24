/**
 * Phase 0 PR-B review P1 regression: patient login/activation install an
 * access-only session via auth store's replaceAccessOnlySession().
 *
 * Starting from a live staff session (access + refresh + profile) the
 * replacement must:
 *   (a) drop the stale staff refresh_token so /authentication/refresh is
 *       NEVER replayed with it — otherwise the backend resolves the old
 *       staff user and mints a fresh staff access token while the UI keeps
 *       showing the patient profile (hidden principal swap);
 *   (b) survive a refresh that was already in flight when the session was
 *       replaced: the rotated tokens of the replaced principal must not be
 *       written back over the patient session.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';

const tokenState = vi.hoisted(() => ({
  access: null as string | null,
  refresh: null as string | null,
  user: null as Record<string, unknown> | null,
  cleared: 0,
}));

vi.mock('../../utils/tokenManager', () => ({
  tokenManager: {
    getAccessToken: () => tokenState.access,
    getRefreshToken: () => tokenState.refresh,
    setAccessToken: (t: string | null) => {
      tokenState.access = t;
    },
    setRefreshToken: (t: string | null) => {
      tokenState.refresh = t;
    },
    setUserData: (u: Record<string, unknown> | null) => {
      tokenState.user = u as Record<string, unknown> | null;
    },
    getUserData: () => tokenState.user,
    hasToken: () => !!tokenState.access,
    isTokenValid: () => !!tokenState.access,
    clearAll: () => {
      tokenState.access = null;
      tokenState.refresh = null;
      tokenState.user = null;
      tokenState.cleared += 1;
    }
  }
}));

vi.mock('../../utils/logger', () => ({
  default: {
    log: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
    debug: vi.fn()
  }
}));

import axios from 'axios';
import { api, getAuthSessionGeneration, type AuthSessionRequestConfig } from '../client';
import { replaceAccessOnlySession } from '../../stores/auth';

// Some sibling suites stub the global URL with a non-constructor; capture the
// real one at import time and restore it per test so the axios pipeline can
// build request URLs regardless of suite order.
const RealURL = URL;

function createJwt(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({
    sub: '1',
    exp: Math.floor(Date.now() / 1000) + expSecondsFromNow,
  }));
  return `${header}.${payload}.signature`;
}

function make200(data: unknown): AxiosResponse {
  return {
    status: 200,
    statusText: 'OK',
    headers: {},
    data,
    config: {} as never
  } as AxiosResponse;
}

function make401(configUrl: string, method = 'get'): AxiosError {
  const config = {
    url: configUrl,
    method,
    headers: AxiosHeaders.from({ Authorization: 'Bearer placeholder' })
  } as never;
  const response: Partial<AxiosResponse> = {
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    data: { detail: 'Not authenticated' },
    config
  };
  return new AxiosError(
    'Request failed with status code 401',
    'ERR_BAD_REQUEST',
    config,
    null,
    response as AxiosResponse
  );
}

/**
 * 401 carrying the REAL request config (like the browser xhr adapter does).
 * Using a static config here would put a placeholder Authorization into
 * failedToken and silently bypass the failedToken === liveToken cleanup
 * comparison — the race test must reproduce the production interceptor
 * inputs exactly.
 */
function make401FromRealConfig(config: InternalAxiosRequestConfig): AxiosError {
  const response: Partial<AxiosResponse> = {
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    data: { detail: 'Not authenticated' },
    config
  };
  return new AxiosError(
    'Request failed with status code 401',
    'ERR_BAD_REQUEST',
    config,
    null,
    response as AxiosResponse
  );
}

function makeStatusErrorFromRealConfig(
  config: InternalAxiosRequestConfig,
  status: number
): AxiosError {
  const response: Partial<AxiosResponse> = {
    status,
    statusText: status === 403 ? 'Forbidden' : 'Internal Server Error',
    headers: {},
    data: { detail: 'Synthetic request failed' },
    config
  };
  return new AxiosError(
    `Request failed with status code ${status}`,
    'ERR_BAD_RESPONSE',
    config,
    null,
    response as AxiosResponse
  );
}

const PATIENT_PROFILE = { id: 42, username: 'patient-42', role: 'Patient' } as Record<string, unknown>;

const originalAdapter = api.defaults.adapter;
const originalPost = axios.post;
const originalGet = axios.get;

beforeEach(() => {
  globalThis.URL = RealURL as unknown as typeof URL;
  delete api.defaults.headers.common['Authorization'];
  // Live staff principal (as after a staff login via LoginFormStyled):
  // access token + refresh token + profile.
  tokenState.access = createJwt(3600);
  tokenState.refresh = 'staff-refresh-token';
  tokenState.user = { id: 1, username: 'registrar', role: 'Registrar' } as Record<string, unknown>;
  tokenState.cleared = 0;
});

afterEach(() => {
  api.defaults.adapter = originalAdapter;
  axios.post = originalPost;
  axios.get = originalGet;
  vi.restoreAllMocks();
});

describe('access-only patient session replacement (P1)', () => {
  it('never replays the stale staff refresh token after a patient login', async () => {
    // Patient JWT inside the "expiring soon" window: the proactive refresh
    // path would fire on the next ordinary request IF any refresh token had
    // survived the replacement.
    const patientJwt = createJwt(120);
    replaceAccessOnlySession(patientJwt, PATIENT_PROFILE);

    // The replacement cleared the old principal's refresh token...
    expect(tokenState.refresh).toBeNull();
    expect(tokenState.access).toBe(patientJwt);
    expect(tokenState.user).toEqual(PATIENT_PROFILE);

    const refreshSpy = vi.spyOn(axios, 'post');
    const seenAuthHeaders: Array<string | undefined> = [];
    api.defaults.adapter = async (config) => {
      seenAuthHeaders.push(config.headers?.Authorization as string);
      return make200({ ok: true });
    };

    // Ordinary patient API request with the token nearing expiry.
    await api.get('/api/v1/patients/appointments');

    // ...the request proceeded under the patient principal...
    expect(seenAuthHeaders[0]).toBe(`Bearer ${patientJwt}`);
    // ...and /authentication/refresh was NEVER called — the stale staff
    // refresh token cannot mint a fresh staff access token anymore.
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(tokenState.access).toBe(patientJwt);
  });

  it('drops rotated tokens of a refresh that was in flight during the replacement', async () => {
    // Staff token expiring soon + refresh token present → the first ordinary
    // request starts a proactive refresh (single-flight).
    tokenState.access = createJwt(120);

    const refreshResolvers: Array<(value: AxiosResponse) => void> = [];
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    vi.spyOn(axios, 'post').mockImplementation(
      () => new Promise<AxiosResponse>((resolve) => {
        refreshResolvers.push(resolve);
      })
    );

    api.defaults.adapter = async () => make200({ ok: true });

    const requestPromise = api.get('/api/v1/patients/appointments');

    // Flush microtasks until the refresh POST is actually in flight.
    for (let i = 0; i < 100 && refreshResolvers.length === 0; i++) {
      await Promise.resolve();
    }
    expect(refreshResolvers.length).toBe(1);

    // While the staff refresh is pending, the patient logs in: session
    // replaced, staff refresh token cleared.
    const patientJwt = createJwt(3600);
    replaceAccessOnlySession(patientJwt, PATIENT_PROFILE);
    expect(tokenState.refresh).toBeNull();

    // The in-flight staff refresh resolves with ROTATED staff tokens.
    refreshResolvers[0](
      make200({ access_token: 'rotated-staff-access', refresh_token: 'rotated-staff-refresh' })
    );

    await expect(requestPromise).rejects.toMatchObject({ code: 'ERR_CANCELED' });

    // The rotated tokens of the replaced principal must NOT resurrect:
    // no staff access token over the patient one, no staff refresh token
    // written back into storage.
    expect(tokenState.access).toBe(patientJwt);
    expect(tokenState.refresh).toBeNull();
    expect(tokenState.cleared).toBe(0);
  });

  it.each([200, 403, 500])(
    'cancels a stale HTTP %i response after the session is replaced',
    async (status) => {
      let requestStarted = false;
      let releaseResponse: () => void = () => {
        throw new Error('The request adapter did not start');
      };
      api.defaults.adapter = async (config) => new Promise<AxiosResponse>((resolve, reject) => {
        requestStarted = true;
        releaseResponse = () => {
          const response: AxiosResponse = {
            status,
            statusText: status === 200 ? 'OK' : status === 403 ? 'Forbidden' : 'Internal Server Error',
            headers: {},
            data: { source: 'old-session' },
            config
          };
          if (status === 200) resolve(response);
          else reject(makeStatusErrorFromRealConfig(config, status));
        };
      });

      const consumeResponse = vi.fn((data: unknown) => data);
      const requestPromise = api.get('/api/v1/patients/appointments')
        .then((response) => consumeResponse(response.data));

      await vi.waitFor(() => expect(requestStarted).toBe(true));

      const patientJwt = createJwt(7200);
      replaceAccessOnlySession(patientJwt, PATIENT_PROFILE);
      releaseResponse();

      await expect(requestPromise).rejects.toMatchObject({ code: 'ERR_CANCELED' });
      expect(consumeResponse).not.toHaveBeenCalled();
      expect(tokenState.access).toBe(patientJwt);
      expect(tokenState.refresh).toBeNull();
      expect(tokenState.cleared).toBe(0);
    }
  );

  it.each([
    {
      name: 'auth bootstrap',
      url: '/api/v1/authentication/login',
      data: { username: 'synthetic-user', password: 'synthetic-password' }
    },
    {
      name: 'pending 2FA challenge',
      url: '/api/v1/2fa/verify',
      data: { pending_2fa_token: 'synthetic-pending-marker', totp_code: '000000' }
    }
  ])('preserves successful $name responses across a session replacement', async ({ url, data }) => {
    let requestStarted = false;
    let releaseResponse: () => void = () => {
      throw new Error('The request adapter did not start');
    };
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    api.defaults.adapter = async (config) => new Promise<AxiosResponse>((resolve) => {
      requestStarted = true;
      releaseResponse = () => resolve({
        status: 200,
        statusText: 'OK',
        headers: {},
        data: { authentication: 'accepted' },
        config
      });
    });

    const consumeResponse = vi.fn((response: unknown) => response);
    const requestPromise = api.post(url, data).then((response) => consumeResponse(response.data));
    await vi.waitFor(() => expect(requestStarted).toBe(true));

    tokenState.access = createJwt(7200);
    tokenState.refresh = 'replacement-refresh-token';
    releaseResponse();

    await expect(requestPromise).resolves.toEqual({ authentication: 'accepted' });
    expect(consumeResponse).toHaveBeenCalledTimes(1);
  });

  it.each(['/api/v1/webauthn/login/begin', '/api/v1/webauthn/login/finish'])(
    'does not refresh or clear an existing session when %s rejects',
    async (url) => {
      tokenState.access = createJwt(120);
      const priorAccess = tokenState.access;
      const refreshSpy = vi.spyOn(axios, 'post');
      vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
      api.defaults.adapter = async (config) => { throw make401FromRealConfig(config); };

      await expect(api.post(url, { patient_id: 42 })).rejects.toMatchObject({
        response: { status: 401 },
      });

      expect(refreshSpy).not.toHaveBeenCalled();
      expect(tokenState.access).toBe(priorAccess);
      expect(tokenState.refresh).toBe('staff-refresh-token');
      expect(tokenState.cleared).toBe(0);
    },
  );

  it.each([
    ['/api/v1/webauthn/login/discoverable/begin', 120, 200],
    ['/api/v1/webauthn/login/discoverable/finish', 120, 200],
    ['/api/v1/webauthn/login/discoverable/begin', -60, 200],
    ['/api/v1/webauthn/login/discoverable/finish', -60, 200],
    ['/api/v1/webauthn/login/discoverable/begin', 120, 401],
    ['/api/v1/webauthn/login/discoverable/finish', 120, 401],
    ['/api/v1/webauthn/login/discoverable/begin', -60, 401],
    ['/api/v1/webauthn/login/discoverable/finish', -60, 401],
    ['/api/v1/webauthn/login/discoverable/complete', 120, 200],
    ['/api/v1/webauthn/login/discoverable/complete', -60, 200],
    ['/api/v1/webauthn/login/discoverable/complete', 120, 401],
    ['/api/v1/webauthn/login/discoverable/complete', -60, 401],
  ])('keeps staff session unchanged for discoverable %s with expiry %i and status %i', async (url, expiry, status) => {
    tokenState.access = createJwt(expiry);
    const originalAccess = tokenState.access;
    const originalUser = tokenState.user;
    const refreshSpy = vi.spyOn(axios, 'post').mockResolvedValue(make200({ access_token: 'unexpected-refresh' }));
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => {
      if (status === 401) throw make401FromRealConfig(config);
      return { ...make200({ ok: true }), config };
    });
    api.defaults.adapter = adapter;

    const request = api.post(url, {});
    if (status === 401) {
      await expect(request).rejects.toMatchObject({ response: { status: 401 } });
    } else {
      await expect(request).resolves.toMatchObject({ data: { ok: true } });
    }
    expect(adapter).toHaveBeenCalledTimes(1);
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(tokenState.access).toBe(originalAccess);
    expect(tokenState.refresh).toBe('staff-refresh-token');
    expect(tokenState.user).toEqual(originalUser);
    expect(tokenState.cleared).toBe(0);
  });

  it.each([
    { url: '/webauthn/login/discoverable/complete', method: 'get' as const },
    { url: '/webauthn/login/discoverable/complete/other', method: 'post' as const },
  ])('does not exempt an unrelated complete-shaped request from session binding: $url', async ({ url, method }) => {
    tokenState.access = createJwt(-60);
    const refreshed = createJwt(3600);
    const refreshSpy = vi.spyOn(axios, 'post').mockResolvedValue(make200({ access_token: refreshed }));
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.request({ url, method, data: {} });
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(tokenState.access).toBe(refreshed);
  });

  it.each([200, 401])('does not refresh or clear an old session for email verification response %s', async (status) => {
    tokenState.access = createJwt(-60);
    const oldToken = tokenState.access;
    const refresh = vi.spyOn(axios, 'post');
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    api.defaults.adapter = async (config) => {
      expect(config.headers.get('Authorization')).toBeUndefined();
      if (status === 401) throw make401FromRealConfig(config);
      return { ...make200({ success: true }), config };
    };
    const request = api.post('/authentication/email-verification/confirm', { token: 'synthetic' });
    if (status === 401) await expect(request).rejects.toMatchObject({ response: { status } });
    else await expect(request).resolves.toMatchObject({ data: { success: true } });
    expect(refresh).not.toHaveBeenCalled();
    expect(tokenState.access).toBe(oldToken);
    expect(tokenState.cleared).toBe(0);
  });

  it.each([
    ['/2fa/setup', 120, 200, false], ['/2fa/setup', -60, 200, false],
    ['/2fa/setup', 120, 401, false], ['/2fa/setup', -60, 401, false],
    ['/2fa/setup', 120, 200, true], ['/2fa/setup', -60, 401, true],
    ['/2fa/verify-setup', 120, 200, false], ['/2fa/verify-setup', -60, 200, false],
    ['/2fa/verify-setup', 120, 401, false], ['/2fa/verify-setup', -60, 401, false],
    ['/api/v1/2fa/verify-setup', 120, 200, true], ['/api/v1/2fa/verify-setup', -60, 401, true],
  ])('preserves the old session for enrollment bootstrap %s expiry %i status %i serialized %s', async (url, expiry, status, serialized) => {
    tokenState.access = createJwt(expiry);
    const originalAccess = tokenState.access;
    const originalUser = tokenState.user;
    const refreshSpy = vi.spyOn(axios, 'post').mockResolvedValue(make200({ access_token: 'unexpected-refresh' }));
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => {
      if (status === 401) throw make401FromRealConfig(config);
      return { ...make200({ ok: true }), config };
    });
    api.defaults.adapter = adapter;
    const body = { enrollment_token: 'synthetic-enrollment-token', totp_code: '000000' };
    const request = api.post(url, serialized ? JSON.stringify(body) : body);
    if (status === 401) await expect(request).rejects.toMatchObject({ response: { status: 401 } });
    else await expect(request).resolves.toMatchObject({ data: { ok: true } });
    expect(adapter).toHaveBeenCalledTimes(1);
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(tokenState.access).toBe(originalAccess);
    expect(tokenState.refresh).toBe('staff-refresh-token');
    expect(tokenState.user).toEqual(originalUser);
    expect(tokenState.cleared).toBe(0);
  });

  it.each([
    ['/2fa/setup', 200], ['/2fa/setup', 401],
    ['/2fa/verify-setup', 200], ['/2fa/verify-setup', 401],
  ])('does not discard %s enrollment response or clear a replacement session on %i', async (url, status) => {
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const refreshSpy = vi.spyOn(axios, 'post');
    let resolveRequest!: (value: AxiosResponse) => void;
    let rejectRequest!: (reason: unknown) => void;
    let actualConfig!: InternalAxiosRequestConfig;
    const adapter = vi.fn((config: InternalAxiosRequestConfig) => {
      actualConfig = config;
      return new Promise<AxiosResponse>((resolve, reject) => { resolveRequest = resolve; rejectRequest = reject; });
    });
    api.defaults.adapter = adapter;
    const request = api.post(url, { enrollment_token: 'synthetic-enrollment-token' });
    // Attach a rejection handler before completing the adapter to avoid an unhandled promise.
    const outcome = request.then((value) => ({ value }), (error: unknown) => ({ error }));
    await vi.waitFor(() => expect(adapter).toHaveBeenCalledTimes(1));
    const replacement = createJwt(7200);
    tokenState.access = replacement;
    tokenState.refresh = 'new-session-refresh';
    tokenState.user = { id: 2, role: 'Doctor' };
    if (status === 401) rejectRequest(make401FromRealConfig(actualConfig));
    else resolveRequest({ ...make200({ ok: true }), config: actualConfig });
    const result = await outcome;
    if (status === 401) expect(result).toMatchObject({ error: { response: { status: 401 } } });
    else expect(result).toMatchObject({ value: { data: { ok: true } } });
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(tokenState.access).toBe(replacement);
    expect(tokenState.refresh).toBe('new-session-refresh');
    expect(tokenState.user).toEqual({ id: 2, role: 'Doctor' });
    expect(tokenState.cleared).toBe(0);
  });

  it.each([
    { url: '/2fa/setup', data: {} },
    { url: '/2fa/verify-setup', data: { totp_code: '000000' } },
    { url: '/2fa/setup', data: { enrollment_token: '' } },
    { url: '/2fa/verify-setup', data: { enrollment_token: '  ' } },
    { url: '/2fa/setup', data: { enrollment_token: 123 } },
    { url: '/2fa/setup', data: '{invalid-json' },
    { url: '/2fa/setup/other', data: { enrollment_token: 'synthetic-enrollment-token' } },
    { url: '/2fa/backup-codes/regenerate', data: { enrollment_token: 'synthetic-enrollment-token' } },
  ])('keeps bearer-only or unrelated requests session-bound: $url', async ({ url, data }) => {
    tokenState.access = createJwt(-60);
    const refreshed = createJwt(3600);
    const refreshSpy = vi.spyOn(axios, 'post').mockResolvedValue(make200({ access_token: refreshed }));
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.post(url, data);
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(tokenState.access).toBe(refreshed);
    expect(adapter).toHaveBeenCalledTimes(1);
  });

  it('does not treat a non-POST enrollment-shaped request as a bootstrap', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    tokenState.access = createJwt(-60);
    const refreshed = createJwt(3600);
    const refreshSpy = vi.spyOn(axios, 'post').mockResolvedValue(make200({ access_token: refreshed }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.request({ url: '/2fa/setup', method: 'get', data: { enrollment_token: 'synthetic-enrollment-token' } });
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(tokenState.access).toBe(refreshed);
  });

  it.each([
    '/webauthn/register/begin', '/webauthn/register/finish',
    '/webauthn/login/begin', '/webauthn/login/finish',
    '/webauthn/login/discoverable/begin', '/webauthn/login/discoverable/finish',
    '/webauthn/login/discoverable/complete',
    '/webauthn/credentials/list', '/webauthn/credentials/5/deactivate',
    '/patient-access/request-otp', '/patient-access/verify-otp', '/patient-access/login',
    '/patient-access/activate/request-otp', '/patient-access/activate/confirm',
  ])('sends credentials and CSRF header on patient auth POST %s', async (url) => {
    document.cookie = 'csrf_token=; Max-Age=0; path=/';
    const csrfSpy = vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.post(url, {});
    const config = adapter.mock.calls[0][0];
    expect(config.withCredentials).toBe(true);
    expect(config.headers.get('X-CSRF-Token')).toBe('synthetic-csrf');
    expect(csrfSpy).toHaveBeenCalledWith(expect.stringContaining('/auth/csrf-token'), { withCredentials: true });
  });

  it.each([
    '/2fa/setup', '/2fa/verify-setup', '/2fa/verify', '/2fa/disable',
    '/2fa/backup-codes/regenerate', '/api/v1/2fa/backup-codes/regenerate',
  ])('sends credentials and CSRF header on 2FA POST %s', async (url) => {
    document.cookie = 'csrf_token=; Max-Age=0; path=/';
    const csrfSpy = vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.post(url, {});
    const config = adapter.mock.calls[0][0];
    expect(config.withCredentials).toBe(true);
    expect(config.headers.get('X-CSRF-Token')).toBe('synthetic-csrf');
    expect(csrfSpy).toHaveBeenCalledWith(expect.stringContaining('/auth/csrf-token'), { withCredentials: true });
  });

  it.each(['/2fa/devices/5', '/api/v1/2fa/devices/5'])('sends credentials and CSRF header when revoking device %s', async (url) => {
    document.cookie = 'csrf_token=; Max-Age=0; path=/';
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.delete(url);
    expect(adapter.mock.calls[0][0].withCredentials).toBe(true);
    expect(adapter.mock.calls[0][0].headers.get('X-CSRF-Token')).toBe('synthetic-csrf');
  });

  it.each([
    { url: '/authentication/login', method: 'post' as const },
    { url: '/patients/appointments', method: 'post' as const },
    { url: '/patients/42', method: 'put' as const },
    { url: '/patients/42', method: 'patch' as const },
    { url: '/patients/42', method: 'delete' as const },
    { url: 'patients/42', method: 'post' as const },
  ])('enables credentials for a trusted mutation $method $url', async ({ url, method }) => {
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.request({ url, method });
    expect(adapter.mock.calls[0][0].withCredentials).toBe(true);
    expect(adapter.mock.calls[0][0].headers.get('X-CSRF-Token')).toBe('synthetic-csrf');
  });

  it.each([
    { url: '/patients/appointments', method: 'get' as const },
    { url: 'https://other.example/patients', method: 'post' as const },
    { url: '//other.example/patients', method: 'post' as const },
    { url: '/patients', method: 'post' as const, baseURL: 'https://other.example' },
    { url: '/\\other.example/patients', method: 'post' as const },
    { url: '/%2f%2fother.example/patients', method: 'post' as const },
    { url: '/%5cother.example/patients', method: 'post' as const },
    { url: '/%0aother.example/patients', method: 'post' as const },
    { url: '/../../outside-api', method: 'post' as const },
    { url: '/patients\n/appointments', method: 'post' as const },
  ])('does not send automatic credentials to an untrusted request $url', async ({ url, method, baseURL }) => {
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.request({ url, method, ...(baseURL ? { baseURL } : {}) });
    const config = adapter.mock.calls[0][0];
    expect(config.withCredentials).not.toBe(true);
    if (method !== 'get') {
      expect(config.headers.get('Authorization')).toBeUndefined();
      expect(config.headers.get('X-CSRF-Token')).toBeUndefined();
    }
  });

  it('preserves caller credentials on external requests and explicit no-credentials on trusted requests', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config }));
    api.defaults.adapter = adapter;
    await api.post('https://other.example/receive', {}, { headers: { Authorization: 'Bearer caller-owned' }, withCredentials: true });
    expect(adapter.mock.calls[0][0].headers.get('Authorization')).toBe('Bearer caller-owned');
    expect(adapter.mock.calls[0][0].headers.get('X-CSRF-Token')).toBeUndefined();
    await api.post('/patients/appointments', {}, { withCredentials: false });
    expect(adapter.mock.calls[1][0].withCredentials).toBe(false);
  });

  it('sends the CSRF cookie and header on direct staff refresh', async () => {
    document.cookie = 'csrf_token=; Max-Age=0; path=/';
    tokenState.access = createJwt(-60);
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue(make200({ access_token: createJwt(3600) }));
    api.defaults.adapter = async (config) => ({ ...make200({ ok: true }), config });
    await api.get('/patients/appointments');
    expect(refresh).toHaveBeenCalledWith(expect.stringContaining('/authentication/refresh'),
      { refresh_token: 'staff-refresh-token' }, { withCredentials: true, headers: { 'X-CSRF-Token': 'synthetic-csrf' } });
  });

  it('does not send the previous refresh token when the session changes during CSRF bootstrap', async () => {
    document.cookie = 'csrf_token=; Max-Age=0; path=/';
    tokenState.access = createJwt(-60);
    let resolveCsrf!: (value: AxiosResponse) => void;
    vi.spyOn(axios, 'get').mockImplementation(() => new Promise((resolve) => { resolveCsrf = resolve; }));
    const refresh = vi.spyOn(axios, 'post');
    api.defaults.adapter = async (config) => ({ ...make200({ ok: true }), config });
    const request = api.get('/patients/appointments');
    for (let i = 0; i < 100 && !resolveCsrf; i++) await Promise.resolve();
    expect(resolveCsrf).toBeDefined();
    replaceAccessOnlySession(createJwt(3600), PATIENT_PROFILE);
    resolveCsrf(make200({ csrf_token: 'synthetic-csrf' }));
    await expect(request).rejects.toMatchObject({ code: 'ERR_CANCELED' });
    expect(refresh).not.toHaveBeenCalled();
  });

  it('does not refresh the session on an external 401', async () => {
    tokenState.access = createJwt(-60);
    const refresh = vi.spyOn(axios, 'post');
    api.defaults.adapter = async (config) => { throw make401FromRealConfig(config); };
    await expect(api.get('https://other.example/resource')).rejects.toMatchObject({ response: { status: 401 } });
    expect(refresh).not.toHaveBeenCalled();
    expect(tokenState.cleared).toBe(0);
  });

  it('scopes a passkey 429 without Retry-After to the login request', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    api.defaults.adapter = async (config) => {
      if (config.url === '/api/v1/webauthn/login/begin') {
        throw makeStatusErrorFromRealConfig(config, 429);
      }
      return { ...make200({ ok: true }), config };
    };

    await expect(api.post('/api/v1/webauthn/login/begin', { patient_id: 42 }))
      .rejects.toMatchObject({ response: { status: 429 } });
    await expect(api.get('/api/v1/patients/summary')).resolves.toMatchObject({
      data: { ok: true },
    });
  });

  it('does NOT wipe the replaced patient session in the reactive 401 cleanup (round-2 P1 race)', async () => {
    // Deterministic interleaving prescribed by the owner review:
    //   staff access + staff refresh
    //   → business request gets 401
    //   → hold the refresh response pending (snapshot + await already taken
    //     by the interceptor — proven by the refresh being in flight)
    //   → replaceAccessOnlySession(Patient)
    //   → resolve the old staff refresh (guard drops rotated credentials)
    //   → the post-await cleanup decision must keep the patient session.
    const staffJwt = createJwt(3600);
    expect(tokenState.access).toBe(staffJwt);
    expect(tokenState.refresh).toBe('staff-refresh-token');

    api.defaults.adapter = async (config) => {
      const url = String(config.url || '');
      if (url.includes('/visits/')) throw make401FromRealConfig(config);
      throw new Error(`unexpected adapter call: ${url}`);
    };

    const refreshResolvers: Array<(value: AxiosResponse) => void> = [];
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    vi.spyOn(axios, 'post').mockImplementation(
      () => new Promise<AxiosResponse>((resolve) => {
        refreshResolvers.push(resolve);
      })
    );

    const requestPromise = api.get('/api/v1/visits/42');

    // Flush microtasks until the reactive refresh POST is actually in
    // flight — the interceptor has taken its pre-await state and is parked
    // inside `await forceRefreshToken()`.
    for (let i = 0; i < 100 && refreshResolvers.length === 0; i++) {
      await Promise.resolve();
    }
    expect(refreshResolvers.length).toBe(1);

    // The patient logs in while the staff refresh is pending. The patient
    // JWT must differ from the staff one BYTE-WISE (distinct exp) —
    // otherwise failedToken === liveToken degenerates to string equality of
    // two identical tokens and the test proves nothing.
    const patientJwt = createJwt(7200);
    replaceAccessOnlySession(patientJwt, PATIENT_PROFILE);
    expect(tokenState.access).toBe(patientJwt);
    expect(patientJwt).not.toBe(staffJwt);
    expect(tokenState.refresh).toBeNull();

    // The stale staff refresh resolves with rotated credentials;
    // performTokenRefresh correctly drops them (returns null).
    refreshResolvers[0](
      make200({ access_token: 'rotated-staff-access', refresh_token: 'rotated-staff-refresh' })
    );

    // The old request is canceled after the session changes; its stale staff
    // refresh must neither replay it as the patient nor clear the patient.
    await expect(requestPromise).rejects.toMatchObject({ code: 'ERR_CANCELED' });

    // Patient session survives:
    expect(tokenState.access).toBe(patientJwt);
    expect(tokenState.refresh).toBeNull();
    expect(tokenState.user).toEqual(PATIENT_PROFILE);
    // clearAll() was NOT called — the pre-await snapshot would have matched
    // failedToken and wiped everything.
    expect(tokenState.cleared).toBe(0);
    // Rotated staff tokens were not installed either.
    expect(tokenState.access).not.toBe('rotated-staff-access');
    expect(tokenState.refresh).not.toBe('rotated-staff-refresh');
  });

  it('still clears a genuinely dead staff session (no replacement) after a failed reactive refresh', async () => {
    // Guard against over-correcting: without a mid-flight replacement the
    // live token still equals failedToken → cleanup must happen as before.
    const staffJwt = createJwt(3600);
    expect(tokenState.access).toBe(staffJwt);

    api.defaults.adapter = async (config) => {
      const url = String(config.url || '');
      if (url.includes('/visits/')) throw make401FromRealConfig(config);
      throw new Error(`unexpected adapter call: ${url}`);
    };
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    vi.spyOn(axios, 'post').mockRejectedValue(
      make401('/api/v1/authentication/refresh', 'post')
    );

    await expect(api.get('/api/v1/visits/42')).rejects.toMatchObject({
      response: { status: 401 }
    });
    // N2-5 review round 3 (P1): the staff dead-session now terminates
    // through the SAME machinery as the access-only path — the auth-store
    // listener (clearToken → clearAll) PLUS the idempotent client-level
    // fallback clear. The clear count is therefore >= 1 (the
    // belt-and-suspenders double-clear when the store listener is
    // loaded, as in this suite).
    expect(tokenState.cleared).toBeGreaterThanOrEqual(1);
    expect(tokenState.access).toBeNull();
  });

  it('terminates a dead access-only session through the auth store on 401 (Phase 0 follow-up)', async () => {
    // Patient portal lifecycle: the session is access-only (no refresh
    // token), so the reactive refresh branch never runs. The 401 cleanup
    // must go through stores/auth.clearToken — clearing auth_token /
    // auth_profile plus tokenManager and notifying subscribers — so
    // RouteAccessBoundary redirects immediately instead of showing a
    // zombie logged-in patient until the next navigation.
    const patientJwt = createJwt(3600);
    replaceAccessOnlySession(patientJwt, PATIENT_PROFILE);
    expect(tokenState.refresh).toBeNull();
    expect(sessionStorage.getItem('auth_token')).toBe(patientJwt);

    api.defaults.adapter = async (config) => {
      throw make401FromRealConfig(config);
    };

    const authEvents: Array<Record<string, unknown>> = [];
    const onAuthChanged = (event: Event): void => {
      authEvents.push((event as CustomEvent).detail as Record<string, unknown>);
    };
    window.addEventListener('authStateChanged', onAuthChanged);
    try {
      await expect(api.get('/api/v1/patients/summary')).rejects.toMatchObject({
        response: { status: 401 }
      });

      // Store-level termination: both session keys are gone...
      expect(sessionStorage.getItem('auth_token')).toBeNull();
      expect(sessionStorage.getItem('auth_profile')).toBeNull();
      // ...tokenManager credentials dropped...
      expect(tokenState.access).toBeNull();
      expect(tokenState.user).toBeNull();
      expect(tokenState.cleared).toBeGreaterThanOrEqual(1);
      // ...and subscribers were notified with the emptied auth state.
      expect(authEvents.length).toBeGreaterThan(0);
      const lastState = authEvents[authEvents.length - 1];
      expect(lastState.token).toBeNull();
      expect(lastState.profile).toBeNull();
    } finally {
      window.removeEventListener('authStateChanged', onAuthChanged);
    }
  });
});

describe('expected session generation', () => {
  const endpoint = '/api/v1/patients/booking-requests/synthetic-request/resubmit';
  const body = { expected_version: 2, appointment_time: '09:40' };

  it('cancels a queued booking mutation before binding to a replacement session', async () => {
    replaceAccessOnlySession(createJwt(3600), PATIENT_PROFILE);
    const config: AuthSessionRequestConfig = {
      expectedAuthSessionGeneration: getAuthSessionGeneration(),
    };
    const csrf = vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue(make200({}));
    const adapter = vi.fn(async (request: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config: request }));
    api.defaults.adapter = adapter;

    // Axios queues the async request interceptor after the caller returns.
    const replacement = Promise.resolve().then(() => {
      replaceAccessOnlySession(createJwt(7200), { id: 43, username: 'patient-43', role: 'Patient' });
    });
    const request = api.post(endpoint, body, config);

    await expect(request).rejects.toMatchObject({ code: 'ERR_CANCELED' });
    await replacement;
    expect(adapter).not.toHaveBeenCalled();
    expect(csrf).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
  });

  it('sends a matched mutation without serializing the expected generation', async () => {
    const token = createJwt(3600);
    replaceAccessOnlySession(token, PATIENT_PROFILE);
    const config: AuthSessionRequestConfig = {
      expectedAuthSessionGeneration: getAuthSessionGeneration(),
      headers: { 'Idempotency-Key': 'synthetic-retry-key' },
    };
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'synthetic-csrf' }));
    const adapter = vi.fn(async (request: InternalAxiosRequestConfig) => ({ ...make200({ ok: true }), config: request }));
    api.defaults.adapter = adapter;

    await expect(api.post(endpoint, body, config)).resolves.toMatchObject({ data: { ok: true } });
    expect(adapter).toHaveBeenCalledTimes(1);
    const [sent] = adapter.mock.calls[0];
    expect(sent.headers.get('Authorization')).toBe('Bearer ' + token);
    expect(sent.headers.get('Idempotency-Key')).toBe('synthetic-retry-key');
    expect(sent.headers.has('expectedAuthSessionGeneration')).toBe(false);
    expect(sent.data).toBe(JSON.stringify(body));
  });
});
