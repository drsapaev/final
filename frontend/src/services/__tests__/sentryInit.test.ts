/**
 * Owner round-12 P1 (PR #3345) — initSentry wiring: the scrubbing contract
 * must actually be attached to the SDK, including beforeSendTransaction
 * (pageload/navigation traces bypass `beforeSend` entirely and carry the
 * full URL — request.url — plus http span descriptions).
 *
 * The SDK is mocked; the DSN env var is stubbed BEFORE the dynamic import
 * because services/sentry.ts reads it at module evaluation time. The stub
 * value is a plain truthy word on purpose: initSentry() only checks
 * truthiness, and a DSN-shaped fake literal (user@host/id) trips secret
 * scanners (GitGuardian) on every push.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { initMock } = vi.hoisted(() => ({ initMock: vi.fn() }));

vi.mock('@sentry/react', () => ({
  init: initMock,
  browserTracingIntegration: vi.fn(() => ({})),
  replayIntegration: vi.fn(() => ({})),
}));

type HookOptions = {
  beforeSend?: (event: unknown) => unknown;
  beforeSendTransaction?: (event: unknown) => unknown;
};

type FakeSpan = { description?: unknown; data?: Record<string, unknown> };
type FakeEvent = {
  type?: string;
  transaction?: string;
  request?: Record<string, unknown>;
  spans?: FakeSpan[];
  breadcrumbs?: Array<Record<string, unknown>>;
  extra?: Record<string, unknown>;
};

describe('initSentry scrubbing wiring (owner round-12 P1)', () => {
  beforeEach(() => {
    // services/sentry.ts is stateful (isInitialized guard) and reads the
    // DSN at module evaluation time — reset the registry so every test
    // re-imports a fresh module AFTER stubbing the env.
    vi.resetModules();
    initMock.mockClear();
    vi.unstubAllEnvs();
  });

  it('registers beforeSend and beforeSendTransaction when a DSN is set', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    expect(initMock).toHaveBeenCalledTimes(1);
    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    expect(typeof options.beforeSend).toBe('function');
    expect(typeof options.beforeSendTransaction).toBe('function');
  });

  it('beforeSendTransaction redacts the credential in request.url, transaction name and span descriptions', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event: FakeEvent = {
      type: 'transaction',
      transaction: '/patient/activate?token=SECRET123',
      request: { url: 'https://app.example.com/patient/activate?token=SECRET123&lang=ru' },
      spans: [
        { description: 'GET https://api.example.com/patients/activate?token=SECRET123', data: { url: '/x?token=SECRET123' } },
        { description: 'db.query' },
        { description: 42 },
      ],
      extra: { note: 'payload' },
    };

    const scrubbed = options.beforeSendTransaction!(event) as FakeEvent;

    expect(scrubbed.transaction).toBe('/patient/activate?token=[REDACTED]');
    expect(scrubbed.request!.url).toBe(
      'https://app.example.com/patient/activate?token=[REDACTED]&lang=ru'
    );
    expect(scrubbed.spans![0].description).toBe(
      'GET https://api.example.com/patients/activate?token=[REDACTED]'
    );
    expect(scrubbed.spans![0].data).toEqual({ url: '/x?token=[REDACTED]' });
    // Non-string and absent descriptions pass through untouched.
    expect(scrubbed.spans![1].description).toBe('db.query');
    expect(scrubbed.spans![2].description).toBe(42);
  });

  it('beforeSend redacts credential query params inside request.url strings too', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event: FakeEvent = {
      request: { url: 'https://app.example.com/patient/activate?token=SECRET123' },
      breadcrumbs: [{ message: 'nav', data: { from: '/patient/activate?token=SECRET123', to: '/x' } }],
    };

    const scrubbed = options.beforeSend!(event) as FakeEvent;

    expect(scrubbed.request!.url).toBe(
      'https://app.example.com/patient/activate?token=[REDACTED]'
    );
    const crumbData = scrubbed.breadcrumbs![0].data as Record<string, unknown>;
    expect(crumbData.from).toBe('/patient/activate?token=[REDACTED]');
    expect(crumbData.to).toBe('/x');
  });
});
