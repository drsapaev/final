/**
 * Reactive 401 recovery in api/client.ts (follow-up to the P0 outage):
 * a 401 from a business endpoint must trigger exactly one single-flight
 * token refresh and a single retry; a failed refresh clears the session
 * only when the failed token is still the current one (login-transition
 * race guard); auth bootstrap endpoints and anonymous requests stay
 * untouched.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios';

const tokenState = vi.hoisted(() => ({
  access: 'old-access-token' as string | null,
  refresh: 'refresh-token-1' as string | null,
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
    clearAll: () => {
      tokenState.access = null;
      tokenState.refresh = null;
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

// Some sibling suites stub the global URL with a non-constructor; capture the
// real one at import time and restore it per test so the axios pipeline can
// build request URLs regardless of suite order.
const RealURL = URL;

function make401(configUrl: string, method = 'get'): AxiosError {
  const config = {
    url: configUrl,
    method,
    headers: AxiosHeaders.from({ Authorization: 'Bearer old-access-token' })
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

function make200(data: unknown): AxiosResponse {
  return {
    status: 200,
    statusText: 'OK',
    headers: {},
    data,
    config: {} as never
  } as AxiosResponse;
}

const originalAdapter = api.defaults.adapter;
const originalPost = axios.post;
const originalGet = axios.get;

beforeEach(() => {
  globalThis.URL = RealURL as unknown as typeof URL;
  tokenState.access = 'old-access-token';
  tokenState.refresh = 'refresh-token-1';
  tokenState.cleared = 0;
});

afterEach(() => {
  api.defaults.adapter = originalAdapter;
  axios.post = originalPost;
  axios.get = originalGet;
  vi.restoreAllMocks();
});

describe('reactive 401 recovery', () => {
  it('refreshes once and retries the business request with the new token', async () => {
    const seenAuthHeaders: Array<string | undefined> = [];
    let businessCalls = 0;

    api.defaults.adapter = async (config) => {
      const url = String(config.url || '');
      if (url.includes('/visits/')) {
        businessCalls += 1;
        seenAuthHeaders.push(config.headers?.Authorization as string);
        if (businessCalls === 1) throw make401(url);
        return make200({ ok: true });
      }
      throw new Error(`unexpected adapter call: ${url}`);
    };

    const refreshSpy = vi
      .spyOn(axios, 'post')
      .mockResolvedValue(
        make200({ access_token: 'new-access-token', refresh_token: 'rotated-refresh' })
      );

    const res = await api.get('/api/v1/visits/42');

    expect(res.data).toEqual({ ok: true });
    expect(businessCalls).toBe(2);
    // The retry must carry the refreshed token.
    expect(seenAuthHeaders[1]).toBe('Bearer new-access-token');
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(tokenState.access).toBe('new-access-token');
    expect(tokenState.refresh).toBe('rotated-refresh');
  });

  it('clears the session when the refresh fails for the current token', async () => {
    api.defaults.adapter = async (config) => {
      const url = String(config.url || '');
      if (url.includes('/visits/')) throw make401(url);
      throw new Error(`unexpected adapter call: ${url}`);
    };
    const refreshSpy = vi
      .spyOn(axios, 'post')
      .mockRejectedValue(make401('/api/v1/authentication/refresh', 'post'));

    await expect(api.get('/api/v1/visits/42')).rejects.toMatchObject({
      response: { status: 401 }
    });
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(tokenState.cleared).toBe(1);
    expect(tokenState.access).toBeNull();
  });

  it('does NOT clear the session when a newer login already replaced the token', async () => {
    api.defaults.adapter = async (config) => {
      const url = String(config.url || '');
      if (url.includes('/visits/')) throw make401(url);
      throw new Error(`unexpected adapter call: ${url}`);
    };
    vi.spyOn(axios, 'post').mockRejectedValue(
      make401('/api/v1/authentication/refresh', 'post')
    );

    // Mid-flight the user re-logged in: current token is no longer the one
    // that went out with the failed request.
    const promise = api.get('/api/v1/visits/42');
    tokenState.access = 'fresh-login-token';

    await expect(promise).rejects.toMatchObject({
      response: { status: 401 }
    });
    expect(tokenState.cleared).toBe(0);
  });

  it('does not attempt refresh for anonymous 401s (no Authorization header)', async () => {
    const refreshSpy = vi.spyOn(axios, 'post');
    api.defaults.adapter = async () => {
      throw make401('/api/v1/visits/42');
    };
    // Simulate no auth header: strip it after the request interceptor runs
    // is not possible here, so emulate by clearing tokens first.
    tokenState.access = null;
    tokenState.refresh = null;

    await expect(api.get('/api/v1/visits/42')).rejects.toMatchObject({
      response: { status: 401 }
    });
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(tokenState.cleared).toBe(0);
  });

  it('never refreshes on auth bootstrap endpoints (login/refresh)', async () => {
    const refreshSpy = vi.spyOn(axios, 'post');
    api.defaults.adapter = async (config) => {
      const url = String(config.url || '');
      if (url.includes('/authentication/login')) throw make401(url, 'post');
      throw new Error(`unexpected adapter call: ${url}`);
    };
    // CSRF bootstrap: cookie is empty in jsdom → mock the csrf fetch.
    vi.spyOn(axios, 'get').mockResolvedValue(make200({ csrf_token: 'csrf' }));

    await expect(
      api.post('/api/v1/authentication/login', { username: 'u', password: 'p' })
    ).rejects.toMatchObject({ response: { status: 401 } });
    // axios.post is the global used for refresh — the only post here is the
    // login itself via the api instance, so the refresh spy must stay empty.
    expect(refreshSpy).not.toHaveBeenCalled();
    expect(tokenState.cleared).toBe(0);
  });
});
