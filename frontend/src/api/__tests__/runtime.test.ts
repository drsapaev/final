import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  buildApiUrl,
  buildWsUrl,
  getApiBaseUrl,
  getApiOrigin,
  getRuntimeResolution,
  getWsBaseUrl,
} from '../runtime';

interface RuntimeResolutionWindow {
  location: { origin: string };
  __CLINIC_RUNTIME__?: {
    currentOrigin: string;
    apiOrigin: string;
    apiBaseUrl: string;
    wsOrigin: string;
  };
}

describe('api runtime resolution', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('respects an explicitly configured VITE_API_BASE_URL over the browser origin', () => {
    // CONTRACT (ops/vps/frontend.env.sample): setting VITE_API_BASE_URL is an
    // intentional separate-API-origin switch (e.g. frontend on Vercel, API on
    // a tunnel/VPS) and must win over same-origin inference.
    vi.stubEnv('VITE_API_BASE_URL', 'https://staging.example.com');
    vi.stubGlobal('window', { location: { origin: 'https://clinic.example.com' } });

    expect(getApiOrigin()).toBe('https://staging.example.com');
    expect(getApiBaseUrl()).toBe('https://staging.example.com/api/v1');
    expect(buildApiUrl('/patients')).toBe('https://staging.example.com/api/v1/patients');
    expect(buildWsUrl('/ws/chat')).toBe('wss://staging.example.com/ws/chat');
  });

  it('prefers the browser origin when no API env is configured (same-origin deploys)', () => {
    vi.stubGlobal('window', { location: { origin: 'https://clinic.example.com' } });

    expect(getApiOrigin()).toBe('https://clinic.example.com');
    expect(getApiBaseUrl()).toBe('https://clinic.example.com/api/v1');
  });

  it('falls back to the canonical backend origin for localhost browser origins', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://staging.example.com');
    vi.stubGlobal('window', { location: { origin: 'http://localhost:3000' } });

    expect(getApiOrigin()).toBe('https://staging.example.com');
    expect(getApiBaseUrl()).toBe('https://staging.example.com/api/v1');
    expect(buildWsUrl('/ws/chat')).toBe('wss://staging.example.com/ws/chat');
  });

  it('derives websocket base from current browser origin', () => {
    vi.stubGlobal('window', { location: { origin: 'https://clinic.example.com' } });

    expect(getWsBaseUrl()).toBe('wss://clinic.example.com');
    expect(buildWsUrl('/ws/chat')).toBe('wss://clinic.example.com/ws/chat');
  });

  it('falls back to env when browser origin is unavailable', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://fallback.example.com');
    vi.stubGlobal('window', undefined);

    expect(getApiOrigin()).toBe('https://fallback.example.com');
    expect(getApiBaseUrl()).toBe('https://fallback.example.com/api/v1');
  });

  it('publishes runtime resolution onto window for smoke probes', () => {
    const windowStub: RuntimeResolutionWindow = { location: { origin: 'https://clinic.example.com' } };
    vi.stubGlobal('window', windowStub);

    expect(getRuntimeResolution()).toEqual({
      currentOrigin: 'https://clinic.example.com',
      apiOrigin: 'https://clinic.example.com',
      apiBaseUrl: 'https://clinic.example.com/api/v1',
      wsOrigin: 'wss://clinic.example.com',
    });
    expect(windowStub.__CLINIC_RUNTIME__).toEqual({
      currentOrigin: 'https://clinic.example.com',
      apiOrigin: 'https://clinic.example.com',
      apiBaseUrl: 'https://clinic.example.com/api/v1',
      wsOrigin: 'wss://clinic.example.com',
    });
  });
});
