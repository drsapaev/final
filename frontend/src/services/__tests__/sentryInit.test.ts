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
  beforeSendSpan?: (span: unknown) => unknown;
  beforeBreadcrumb?: (breadcrumb: unknown) => unknown;
};

type FakeSpan = { description?: unknown; op?: string; data?: Record<string, unknown> };
type FakeEvent = {
  type?: string;
  message?: string;
  transaction?: string;
  fingerprint?: string[];
  request?: Record<string, unknown>;
  spans?: FakeSpan[];
  breadcrumbs?: Array<Record<string, unknown>>;
  extra?: Record<string, unknown>;
  contexts?: Record<string, unknown>;
  logentry?: { message?: string; formatted?: string; params?: unknown[] };
  exception?: { values?: Array<{ type?: string; value?: string }> };
  threads?: { values?: Array<{ stacktrace?: { frames?: Array<{ vars?: Record<string, unknown> }> } }> };
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
    expect(typeof options.beforeSendSpan).toBe('function');
    expect(typeof options.beforeBreadcrumb).toBe('function');
    expect(options.sendDefaultPii).toBe(false);
    expect(options.replaysSessionSampleRate).toBe(0);
    expect(options.replaysOnErrorSampleRate).toBe(0);
  });

  it('beforeSendTransaction removes raw URLs and span descriptions while preserving safe span metrics', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event: FakeEvent = {
      type: 'transaction',
      transaction: '/patient/activate?token=SECRET123',
      request: { url: 'https://app.example.com/patient/activate?token=SECRET123&lang=ru' },
      spans: [
        {
          description: 'GET https://api.example.com/patients/activate?token=SECRET123',
          data: {
            url: '/x?token=SECRET123',
            'http.response.status_code': 503,
            'gen_ai.request.messages': 'TRACE_PROMPT_CANARY',
            'gen_ai.usage.input_tokens': 17,
            'ai.invalid_input_tokens': 'INVALID_TOKEN_DIAGNOSTIC_CANARY',
          },
        },
        { description: 'db.query' },
        { description: 42 },
      ],
      extra: { note: 'payload', system_prompt: 'TRACE_SYSTEM_PROMPT_CANARY' },
      contexts: { response: { status_code: 503, body: 'TRACE_BODY_CANARY' }, ai: { system_prompt: 'TRACE_CONTEXT_PROMPT_CANARY' } },
      breadcrumbs: [{ message: 'TRACE_BREADCRUMB_CANARY' }],
    };

    const scrubbed = options.beforeSendTransaction!(event) as FakeEvent;

    expect(scrubbed.transaction).toBe('[REDACTED TRANSACTION]');
    expect(scrubbed.request).toBeUndefined();
    expect(scrubbed.spans).toEqual([{
      data: {
        'http.response.status_code': 503,
        'gen_ai.usage.input_tokens': 17,
      },
    }]);
    const serialized = JSON.stringify(scrubbed);
    expect(serialized).not.toContain('TRACE_BODY_CANARY');
    expect(serialized).not.toContain('TRACE_BREADCRUMB_CANARY');
    expect(serialized).not.toContain('TRACE_PROMPT_CANARY');
    expect(serialized).not.toContain('TRACE_SYSTEM_PROMPT_CANARY');
    expect(serialized).not.toContain('TRACE_CONTEXT_PROMPT_CANARY');
    expect(scrubbed.contexts!.response).toEqual({ status_code: 503 });
    expect(scrubbed.spans![0].data!['http.response.status_code']).toBe(503);
    expect(scrubbed.spans![0].data!['gen_ai.usage.input_tokens']).toBe(17);
    expect(scrubbed.breadcrumbs).toBeUndefined();
    expect(JSON.stringify(scrubbed)).not.toContain('INVALID_TOKEN_DIAGNOSTIC_CANARY');
  });

  it('beforeSend removes URLs and breadcrumbs from error events', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event: FakeEvent = {
      request: { url: 'https://app.example.com/patient/activate?token=SECRET123' },
      breadcrumbs: [{ message: 'nav', data: { from: '/patient/activate?token=SECRET123', to: '/x' } }],
    };

    const scrubbed = options.beforeSend!(event) as FakeEvent;

    expect(scrubbed.request).toBeUndefined();
    expect(scrubbed.breadcrumbs).toBeUndefined();
  });

  it('beforeSend removes unstructured clinical text and AI payload content', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event: FakeEvent = {
      message: 'CLINICAL_MESSAGE_CANARY',
      request: {
        url: '/api/ai',
        data: {
          prompt: 'AI_PROMPT_CANARY',
          tool_arguments: 'AI_TOOL_ARGS_CANARY',
          content: 'AI_RESPONSE_CANARY',
        },
      },
      breadcrumbs: [
        {
          message: 'CLINICAL_BREADCRUMB_CANARY',
          data: { response: 'AI_BREADCRUMB_RESPONSE_CANARY', action: 'submit' },
        },
      ],
      exception: { values: [{ type: 'ProviderError', value: 'AI_EXCEPTION_CANARY' }] },
      extra: {
        completion: 'AI_EXTRA_CANARY',
        system_prompt: 'SYSTEM_PROMPT_CANARY',
        provider_response: 'PROVIDER_RESPONSE_CANARY',
        input: 'AI_INPUT_CANARY',
        input_tokens: 24,
        invalid_input_tokens: 'INVALID_TOKEN_DIAGNOSTIC_CANARY',
      },
      contexts: { response: { status_code: 503, body: 'HTTP_BODY_CANARY' } },
      spans: [{ description: 'error.span', data: {
        'gen_ai.request.messages': 'SPAN_PROMPT_CANARY',
        'http.response.status_code': 502,
      } }],
      threads: { values: [{ stacktrace: { frames: [{ vars: { note: 'THREAD_LOCAL_CANARY' } }] } }] },
      logentry: {
        message: 'CLINICAL_LOGENTRY_MESSAGE_CANARY',
        formatted: 'CLINICAL_LOGENTRY_FORMAT_CANARY',
        params: ['CLINICAL_LOGENTRY_PARAM_CANARY'],
      },
    };

    const scrubbed = options.beforeSend!(event) as FakeEvent;
    const serialized = JSON.stringify(scrubbed);

    for (const marker of [
      'CLINICAL_MESSAGE_CANARY',
      'AI_PROMPT_CANARY',
      'AI_TOOL_ARGS_CANARY',
      'AI_RESPONSE_CANARY',
      'CLINICAL_BREADCRUMB_CANARY',
      'AI_BREADCRUMB_RESPONSE_CANARY',
      'AI_EXCEPTION_CANARY',
      'AI_EXTRA_CANARY',
      'SYSTEM_PROMPT_CANARY',
      'PROVIDER_RESPONSE_CANARY',
      'AI_INPUT_CANARY',
      'INVALID_TOKEN_DIAGNOSTIC_CANARY',
      'HTTP_BODY_CANARY',
      'SPAN_PROMPT_CANARY',
      'THREAD_LOCAL_CANARY',
      'CLINICAL_LOGENTRY_MESSAGE_CANARY',
      'CLINICAL_LOGENTRY_FORMAT_CANARY',
      'CLINICAL_LOGENTRY_PARAM_CANARY',
    ]) {
      expect(serialized).not.toContain(marker);
    }
    expect(scrubbed.contexts!.response).toEqual({ status_code: 503 });
    expect(scrubbed.spans![0].data!['http.response.status_code']).toBe(502);
    expect(scrubbed.threads).toBeUndefined();
    expect(scrubbed.extra!.input_tokens).toBe(24);
    expect(scrubbed.breadcrumbs).toBeUndefined();

    const diagnosticEvent: FakeEvent = {
      logentry: { message: 'AI provider failed for patient clinical content' },
      extra: {
        diagnostic_code: 'ai_provider_failure',
        provider: 'openai',
        error_type: 'TimeoutError',
      },
    };
    const grouped = options.beforeSend!(diagnosticEvent) as FakeEvent;
    expect(grouped.fingerprint).toEqual([
      '{{ default }}', 'ai_provider_failure', 'openai', 'TimeoutError',
    ]);
  });

  it('drops an event when beforeSend cannot scrub its payload', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event = new Proxy({}, {
      ownKeys() {
        throw new Error('synthetic scrubber failure');
      },
    });

    expect(options.beforeSend!(event)).toBeNull();
  });

  it('drops a transaction when beforeSendTransaction cannot scrub its payload', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event = new Proxy({}, {
      ownKeys() {
        throw new Error('synthetic scrubber failure');
      },
    });

    expect(options.beforeSendTransaction!(event)).toBeNull();
  });

  it('removes arbitrary text from every event channel and preserves safe diagnostics', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const event: FakeEvent & Record<string, unknown> = {
      type: 'transaction',
      event_id: 'a'.repeat(32),
      transaction: '/patients/alice?note=TRANSACTION_QUERY_CANARY',
      transaction_info: { source: 'route' },
      request: {
        method: 'GET',
        url: '/patients?complaint=REQUEST_QUERY_CANARY',
        query_string: 'name=QUERY_CANARY',
        headers: { referer: 'REFERER_CANARY' },
      },
      user: { email: 'PATIENT_EMAIL_CANARY', id: 'PATIENT_ID_CANARY' },
      extra: {
        clinical_summary: 'EXTRA_CANARY',
        diagnostic_code: 'ai_provider_failure',
        provider: 'openai',
        error_type: 'TimeoutError',
        input_tokens: 27,
        model: 'MODEL_CANARY',
      },
      contexts: {
        ai: { summary: 'CUSTOM_CONTEXT_CANARY' },
        response: { status_code: 503, body_size: 42, body: 'RESPONSE_BODY_CANARY' },
      },
      breadcrumbs: [{ message: 'BREADCRUMB_CANARY', data: { details: 'CRUMB_DATA_CANARY' } }],
      spans: [{
        description: 'SPAN_DESCRIPTION_CANARY',
        op: 'http.client',
        data: {
          'http.response.status_code': 502,
          'gen_ai.usage.input_tokens': 19,
          clinical_summary: 'SPAN_DATA_CANARY',
        },
      }],
      tags: { severity: 'error', patient_name: 'TAG_CANARY' },
      custom_payload: 'TOP_LEVEL_CANARY',
      fingerprint: ['PATIENT_FINGERPRINT_CANARY'],
    };

    const scrubbed = options.beforeSendTransaction!(event) as FakeEvent & Record<string, unknown>;
    const serialized = JSON.stringify(scrubbed);
    for (const marker of [
      'TRANSACTION_QUERY_CANARY', 'REQUEST_QUERY_CANARY', 'QUERY_CANARY', 'REFERER_CANARY',
      'PATIENT_EMAIL_CANARY', 'PATIENT_ID_CANARY', 'EXTRA_CANARY', 'MODEL_CANARY',
      'CUSTOM_CONTEXT_CANARY', 'RESPONSE_BODY_CANARY', 'BREADCRUMB_CANARY', 'CRUMB_DATA_CANARY',
      'SPAN_DESCRIPTION_CANARY', 'SPAN_DATA_CANARY', 'TAG_CANARY', 'TOP_LEVEL_CANARY',
      'PATIENT_FINGERPRINT_CANARY',
    ]) {
      expect(serialized).not.toContain(marker);
    }
    expect(scrubbed.request).toEqual({ method: 'GET' });
    expect(scrubbed.user).toBeUndefined();
    expect(scrubbed.breadcrumbs).toBeUndefined();
    expect(scrubbed.contexts).toEqual({ response: { status_code: 503, body_size: 42 } });
    expect(scrubbed.extra).toEqual({
      diagnostic_code: 'ai_provider_failure',
      provider: 'openai',
      error_type: 'TimeoutError',
      input_tokens: 27,
    });
    expect(scrubbed.spans).toEqual([{
      op: 'http.client',
      data: { 'http.response.status_code': 502, 'gen_ai.usage.input_tokens': 19 },
    }]);
    expect(scrubbed.tags).toEqual({ severity: 'error' });
    expect(scrubbed.fingerprint).toEqual([
      '{{ default }}', 'ai_provider_failure', 'openai', 'TimeoutError',
    ]);

    const routeEvent = options.beforeSendTransaction!({
      type: 'transaction',
      transaction: 'GET /api/v1/patients/{patient_id}',
      transaction_info: { source: 'route' },
    }) as FakeEvent & Record<string, unknown>;
    expect(routeEvent.transaction).toBe('GET /api/v1/patients/{patient_id}');
  });

  it('scrubs child spans and drops breadcrumbs at their installed SDK hooks', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'enabled');
    const sentry = await import('../sentry');
    sentry.initSentry();

    const options = initMock.mock.calls[0][0] as Record<string, unknown> & HookOptions;
    const span = options.beforeSendSpan!({
      span_id: 'a'.repeat(16),
      trace_id: 'b'.repeat(32),
      op: 'http.client',
      description: 'CHILD_SPAN_DESCRIPTION_CANARY',
      data: {
        'http.response.status_code': 503,
        'http.url': 'https://host/path?q=CHILD_SPAN_QUERY_CANARY',
      },
    }) as Record<string, unknown>;

    expect(JSON.stringify(span)).not.toContain('CHILD_SPAN_DESCRIPTION_CANARY');
    expect(JSON.stringify(span)).not.toContain('CHILD_SPAN_QUERY_CANARY');
    expect(span).toEqual({
      span_id: 'a'.repeat(16),
      trace_id: 'b'.repeat(32),
      op: 'http.client',
      data: { 'http.response.status_code': 503 },
    });
    expect(options.beforeBreadcrumb!({ message: 'BREADCRUMB_CANARY' })).toBeNull();
  });
});
