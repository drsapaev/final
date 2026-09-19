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
import { type AxiosResponse } from 'axios';

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
});
