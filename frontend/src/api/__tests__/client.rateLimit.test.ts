import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';

const tokenState = vi.hoisted(() => ({ access: 'test-access-token' as string | null, refresh: null as string | null }));

vi.mock('../../utils/tokenManager', () => ({
  tokenManager: {
    getAccessToken: () => tokenState.access,
    getRefreshToken: () => tokenState.refresh,
    setAccessToken: (token: string | null) => { tokenState.access = token; },
    setRefreshToken: (token: string | null) => { tokenState.refresh = token; },
    setUserData: () => undefined,
    getUserData: () => null,
    hasToken: () => Boolean(tokenState.access),
    isTokenValid: () => Boolean(tokenState.access),
    clearAll: () => { tokenState.access = null; tokenState.refresh = null; },
  },
}));

vi.mock('../../utils/logger', () => ({
  default: { log: vi.fn(), warn: vi.fn(), info: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

import { api } from '../client';

const originalAdapter = api.defaults.adapter;

function make429(config: InternalAxiosRequestConfig, retryAfter?: string): AxiosError {
  const response: Partial<AxiosResponse> = {
    status: 429,
    statusText: 'Too Many Requests',
    headers: retryAfter ? AxiosHeaders.from({ 'Retry-After': retryAfter }) : AxiosHeaders.from({}),
    data: { detail: 'Rate limit exceeded.' },
    config,
  };
  return new AxiosError(
    'Request failed with status code 429',
    'ERR_BAD_REQUEST',
    config,
    null,
    response as AxiosResponse,
  );
}

beforeEach(() => {
  tokenState.access = 'test-access-token';
  tokenState.refresh = null;
  window.localStorage.removeItem('clinic_api_rate_limit_until');
  window.localStorage.removeItem('clinic_api_global_rate_limit_until');
});

afterEach(() => {
  api.defaults.adapter = originalAdapter;
});

describe('API 429 cooldown scope', () => {
  it('limits a Retry-After response to the same method and path', async () => {
    const calls: string[] = [];
    api.defaults.adapter = async (config) => {
      calls.push(config.url || '');
      if (config.url === '/api/v1/messages/conversations?unread=true') {
        throw make429(config, '60');
      }
      return {
        status: 200,
        statusText: 'OK',
        headers: AxiosHeaders.from({}),
        data: { ok: true },
        config,
      };
    };

    await expect(api.get('/api/v1/messages/conversations?unread=true'))
      .rejects.toMatchObject({ response: { status: 429 } });
    await expect(api.get('/api/v1/messages/conversations'))
      .rejects.toMatchObject({
        response: {
          status: 429,
          data: { scope: 'request', cooldownMs: expect.any(Number) },
        },
      });
    await expect(api.get('/api/v1/admin/queue-resources'))
      .resolves.toMatchObject({ data: { ok: true } });

    expect(window.localStorage.getItem('clinic_api_global_rate_limit_until')).toBeNull();
    expect(calls).toEqual([
      '/api/v1/messages/conversations?unread=true',
      '/api/v1/admin/queue-resources',
    ]);
  });

  it('does not turn an authentication endpoint 429 into a shared API cooldown', async () => {
    const calls: string[] = [];
    api.defaults.adapter = async (config) => {
      calls.push(config.url || '');
      if (config.url === '/api/v1/authentication/profile') throw make429(config);
      return {
        status: 200,
        statusText: 'OK',
        headers: AxiosHeaders.from({}),
        data: { ok: true },
        config,
      };
    };

    await expect(api.get('/api/v1/authentication/profile'))
      .rejects.toMatchObject({ response: { status: 429 } });
    await expect(api.get('/api/v1/admin/queue-resources'))
      .resolves.toMatchObject({ data: { ok: true } });

    expect(window.localStorage.getItem('clinic_api_global_rate_limit_until')).toBeNull();
    expect(calls).toEqual([
      '/api/v1/authentication/profile',
      '/api/v1/admin/queue-resources',
    ]);
  });

  it('keeps the shared cooldown for a generic API 429 without Retry-After', async () => {
    const calls: string[] = [];
    api.defaults.adapter = async (config) => {
      calls.push(config.url || '');
      if (config.url === '/api/v1/admin/queue-resources') throw make429(config);
      return {
        status: 200,
        statusText: 'OK',
        headers: AxiosHeaders.from({}),
        data: { ok: true },
        config,
      };
    };

    await expect(api.get('/api/v1/admin/queue-resources'))
      .rejects.toMatchObject({ response: { status: 429 } });
    await expect(api.get('/api/v1/directions'))
      .rejects.toMatchObject({
        response: {
          status: 429,
          data: { scope: 'global', cooldownMs: expect.any(Number) },
        },
      });

    expect(window.localStorage.getItem('clinic_api_global_rate_limit_until')).not.toBeNull();
    expect(calls).toEqual(['/api/v1/admin/queue-resources']);
  });
});
