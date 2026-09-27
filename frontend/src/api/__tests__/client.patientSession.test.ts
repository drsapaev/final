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
import { api } from '../client';
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

const PATIENT_PROFILE = { id: 42, username: 'patient-42', role: 'Patient' } as Record<string, unknown>;

const originalAdapter = api.defaults.adapter;
const originalPost = axios.post;
const originalGet = axios.get;

beforeEach(() => {
  globalThis.URL = RealURL as unknown as typeof URL;
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

    await requestPromise;

    // The rotated tokens of the replaced principal must NOT resurrect:
    // no staff access token over the patient one, no staff refresh token
    // written back into storage.
    expect(tokenState.access).toBe(patientJwt);
    expect(tokenState.refresh).toBeNull();
    expect(tokenState.cleared).toBe(0);
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

    // The business request itself still surfaces the original 401 (nothing
    // to retry with — that path is unchanged), but the cleanup must NOT
    // take the replaced session with it.
    await expect(requestPromise).rejects.toMatchObject({ response: { status: 401 } });

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
