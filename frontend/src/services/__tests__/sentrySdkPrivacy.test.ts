import * as Sentry from '@sentry/react';
import { describe, expect, it } from 'vitest';
import { createSentryPrivacyCallbacks } from '../sentry';

type InitOptions = NonNullable<Parameters<typeof Sentry.init>[0]>;

describe('Sentry SDK privacy callbacks (in-memory transport)', () => {
  it('sends only allowlisted error and transaction data through the installed SDK pipeline', async () => {
    const sentEnvelopes: unknown[] = [];
    const callbacks = createSentryPrivacyCallbacks();
    let errorCallbackCalls = 0;
    let transactionCallbackCalls = 0;
    let spanCallbackCalls = 0;
    let breadcrumbCallbackCalls = 0;
    const transport: NonNullable<InitOptions['transport']> = () => ({
      send(envelope) {
        sentEnvelopes.push(envelope);
        return Promise.resolve({ statusCode: 200 });
      },
      flush() {
        return Promise.resolve(true);
      },
    });
    const dsn = ['https:', '', ['public', 'dsn.invalid'].join('@'), '1'].join('/');

    Sentry.init({
      dsn,
      defaultIntegrations: false,
      integrations: [],
      transport,
      sendClientReports: false,
      tracesSampleRate: 1,
      ...callbacks,
      beforeSend(event, hint) {
        errorCallbackCalls += 1;
        return callbacks.beforeSend!(event, hint);
      },
      beforeSendTransaction(event, hint) {
        transactionCallbackCalls += 1;
        return callbacks.beforeSendTransaction!(event, hint);
      },
      beforeSendSpan(span) {
        spanCallbackCalls += 1;
        return callbacks.beforeSendSpan!(span);
      },
      beforeBreadcrumb(breadcrumb, hint) {
        breadcrumbCallbackCalls += 1;
        return callbacks.beforeBreadcrumb!(breadcrumb, hint);
      },
    });

    Sentry.addBreadcrumb({ message: 'SDK_BREADCRUMB_CANARY', data: { clinical_note: 'SDK_CRUMB_DATA_CANARY' } });

    Sentry.captureEvent({
      level: 'error',
      message: 'ERROR_MESSAGE_CANARY',
      request: {
        method: 'GET',
        url: '/patients?complaint=ERROR_QUERY_CANARY',
        headers: { referer: 'ERROR_REFERER_CANARY' },
      },
      user: { email: 'ERROR_EMAIL_CANARY' },
      extra: { diagnosis: 'ERROR_EXTRA_CANARY', diagnostic_code: 'ai_provider_failure', provider: 'openai' },
      contexts: { clinical: { summary: 'ERROR_CONTEXT_CANARY' }, response: { status_code: 503 } },
      breadcrumbs: [{ message: 'ERROR_BREADCRUMB_CANARY', data: { details: 'ERROR_CRUMB_DATA_CANARY' } }],
    } as Parameters<typeof Sentry.captureEvent>[0]);

    Sentry.captureEvent({
      type: 'transaction',
      transaction: '/patients/alice?note=TRACE_QUERY_CANARY',
      transaction_info: { source: 'route' },
      request: { url: '/patients?name=TRACE_REQUEST_CANARY' },
      user: { email: 'TRACE_EMAIL_CANARY' },
      contexts: { response: { status_code: 502, body: 'TRACE_RESPONSE_CANARY' } },
      spans: [{
        span_id: 'a'.repeat(16),
        trace_id: 'b'.repeat(32),
        start_timestamp: 1_761_800_000,
        op: 'http.client',
        description: 'TRACE_SPAN_DESCRIPTION_CANARY',
        data: {
          'http.response.status_code': 502,
          'http.url': 'https://host/path?q=TRACE_SPAN_QUERY_CANARY',
        },
      }],
    } as Parameters<typeof Sentry.captureEvent>[0]);

    await Sentry.flush(2_000);
    const serialized = JSON.stringify(sentEnvelopes);

    expect(sentEnvelopes.length).toBeGreaterThanOrEqual(2);
    expect(errorCallbackCalls).toBe(1);
    expect(transactionCallbackCalls).toBe(1);
    expect(spanCallbackCalls).toBe(1);
    expect(breadcrumbCallbackCalls).toBe(1);
    for (const marker of [
      'ERROR_MESSAGE_CANARY', 'ERROR_QUERY_CANARY', 'ERROR_REFERER_CANARY', 'ERROR_EMAIL_CANARY',
      'ERROR_EXTRA_CANARY', 'ERROR_CONTEXT_CANARY', 'ERROR_BREADCRUMB_CANARY',
      'ERROR_CRUMB_DATA_CANARY', 'TRACE_QUERY_CANARY', 'TRACE_REQUEST_CANARY',
      'TRACE_EMAIL_CANARY', 'TRACE_RESPONSE_CANARY', 'TRACE_SPAN_DESCRIPTION_CANARY',
      'TRACE_SPAN_QUERY_CANARY',
    ]) {
      expect(serialized).not.toContain(marker);
    }
    expect(serialized).toContain('ai_provider_failure');
    expect(serialized).toContain('http.response.status_code');
  });
});
