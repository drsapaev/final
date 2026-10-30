/**
 * Sentry initialization for the clinic frontend.
 *
 * Init is a no-op if VITE_SENTRY_DSN is unset — this lets dev/local runs
 * skip Sentry without code changes. In staging/production, set the DSN via
 * Vercel env vars.
 *
 * Trace sample rate is intentionally low (5%) — this is a medical SaaS where
 * patients hit the app from slow mobile networks; 100% sampling would drown
 * the Sentry quota in noise. Errors are always captured (tracesSampleRate
 * only affects performance traces, not errors).
 *
 * PII scrubbing: Sentry React SDK auto-scrubs `password`, `secret`, `token`
 * keys from payloads. Additional scrubbing for medical fields is done in
 * `beforeSend`; credential query params embedded in URL-valued fields and
 * transactions are redacted in `beforeSend`/`beforeSendTransaction`
 * (owner round-12 P1 — see redactCredentialQueryParams).
 */

import * as Sentry from '@sentry/react';

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
const SENTRY_ENV = import.meta.env.VITE_SENTRY_ENV || 'development';
const SENTRY_TRACES_SAMPLE_RATE = Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || 0.05);

const MEDICAL_PII_KEYS = [
  // Patient identifiers
  'iin', 'passport_number', 'passport_series', 'ssn', 'national_id',
  // Contact info
  'phone', 'phone_number', 'email', 'address', 'street', 'city', 'postal_code',
  // Names (audit/phase-2, BS-57: previously missing — only `patient_name`
  // substring was matched, so standalone `full_name`, `first_name`,
  // `last_name`, `middle_name`, `fio`, `patient_fio` leaked through).
  'full_name', 'firstname', 'first_name', 'lastname', 'last_name',
  'middle_name', 'surname', 'patronymic', 'fio', 'name',
  // Dates of birth (previously missing)
  'birth_date', 'date_of_birth', 'dob', 'patient_birth_date', 'patient_birth_year',
  // Insurance / identity (previously missing)
  'insurance_number', 'card_number', 'cvv', 'payment_method',
  // Medical
  'diagnosis', 'diagnoses', 'icd10', 'icd10_codes', 'complaints', 'complaint',
  'examination', 'prescription', 'medications', 'allergies',
  'medical_history', 'symptoms', 'treatment', 'lab_results', 'blood_type',
  // Visit
  'visit_reason', 'patient_name', 'patient_id', 'doctor_notes',
  // Auth tokens (defence-in-depth: Sentry SDK auto-scrubs these, but the
  // custom scrubber runs first and we want redaction even if SDK behaviour
  // changes in a future release)
  'token', 'access_token', 'refresh_token', 'secret', 'api_key', 'password',
];

// AI content can include clinical notes and tool arguments under generic keys.
const AI_CONTENT_KEYS = [
  'system_prompt', 'systemprompt', 'system_instructions', 'provider_response',
  'providerresponse', 'user_input', 'patient_input', 'input_text', 'output_text',
  'prompt', 'prompts', 'input', 'output', 'response', 'responses', 'content',
  'completion', 'completions', 'messages', 'arguments', 'tool_args', 'tool_arguments',
];
const SAFE_DIAGNOSTIC_SUFFIXES = [
  'status_code', 'body_size', 'model', 'input_tokens', 'output_tokens', 'total_tokens',
];
const SAFE_AI_DIAGNOSTIC_CODES = new Set([
  'ai_gateway_unexpected_error', 'ai_gateway_stream_error', 'ai_provider_failure',
]);

type MutableSentryEvent = Record<string, unknown> & {
  breadcrumbs?: Array<Record<string, unknown>>;
  contexts?: Record<string, unknown>;
  exception?: { values?: Array<Record<string, unknown>> };
  extra?: Record<string, unknown>;
  logentry?: Record<string, unknown>;
  request?: Record<string, unknown>;
  spans?: Array<Record<string, unknown>>;
  threads?: { values?: Array<Record<string, unknown>> };
};

// Credential keys redacted INSIDE URL-shaped strings (owner round-12 P1):
// request.url, breadcrumb from/to, Referer headers and pageload/http-span
// descriptions carry the URL as a plain string, so the key-based scrubber
// above never sees the "token" key. Deliberately narrower than
// MEDICAL_PII_KEYS — non-credential params (sort, q, lang, name…) must
// stay readable for debugging.
const CREDENTIAL_QUERY_KEYS = [
  'token', // also matches *_token via the suffix rule (access_token, refresh_token, activation_token, …)
  'apikey', 'api_key', 'secret', 'password', 'sig', 'signature', 'authorization',
];

/**
 * Redact credential query/fragment params inside a URL-ish string while
 * preserving everything else. Matches `?key=`, `&key=`, `#key=` and a bare
 * leading `key=` (separately-transmitted query_string fields); keys are
 * percent-decoded first, mirroring URLSearchParams so an obfuscated
 * %74oken= is caught too. Generic over the string-ish input so callers
 * keep their precise type (string | undefined for event.transaction, etc.).
 */
export function redactCredentialQueryParams<T extends string | undefined | null>(value: T): T {
  if (typeof value !== 'string' || !value) {
    return value;
  }
  const scrubbed = value.replace(
    /(^|[?&#])([A-Za-z0-9_%.-]+)=([^&#]*)/g,
    (match, sep: string, key: string) => {
      let lowerKey = key.toLowerCase();
      try {
        lowerKey = decodeURIComponent(lowerKey);
      } catch {
        // Malformed percent-encoding — match on the raw key.
      }
      const isCredential = CREDENTIAL_QUERY_KEYS.some(
        (k) => lowerKey === k || lowerKey.endsWith(`_${k}`)
      );
      return isCredential ? `${sep}${key}=[REDACTED]` : match;
    }
  );
  return scrubbed as T;
}

/**
 * Key-based PII scrubbing PLUS credential-query redaction inside string
 * values (owner round-12 P1): URL-valued telemetry fields (request.url,
 * breadcrumb from/to, Referer) hold the URL as a plain string — the
 * key-based loop below cannot catch a `?token=` embedded in it. Exported
 * for unit tests (scrubbing contract is security-relevant).
 */
export function scrubPIIFromObject(obj: unknown, parentKey = ''): unknown {
  if (typeof obj === 'string') {
    return redactCredentialQueryParams(obj);
  }
  if (!obj || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map((item) => scrubPIIFromObject(item, parentKey));

  const cleaned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase().replace(/-/g, '_');
    const isHttpResponseContext = parentKey === 'contexts' && lowerKey === 'response';
    if (isHttpResponseContext) {
      (cleaned as Record<string, unknown>)[key] = scrubHttpResponseContext(value);
      continue;
    }
    const leafKey = lowerKey.split('.').pop() || lowerKey;
    const isDiagnosticField = SAFE_DIAGNOSTIC_SUFFIXES.includes(leafKey) || leafKey.endsWith('_tokens');
    const isSafeDiagnostic = leafKey === 'model'
      ? typeof value === 'string' && /^[A-Za-z0-9_.:/-]{1,80}$/.test(value)
      : isDiagnosticField && typeof value === 'number' && Number.isFinite(value);
    if (isDiagnosticField) {
      (cleaned as Record<string, unknown>)[key] = isSafeDiagnostic ? value : '[REDACTED]';
      continue;
    }
    const containsAiContent =
      !isSafeDiagnostic && AI_CONTENT_KEYS.some((contentKey) => lowerKey.includes(contentKey));
    if (
      containsAiContent ||
      (!isSafeDiagnostic && MEDICAL_PII_KEYS.some((pii) => lowerKey.includes(pii)))
    ) {
      (cleaned as Record<string, unknown>)[key] = '[REDACTED]';
    } else {
      (cleaned as Record<string, unknown>)[key] = scrubPIIFromObject(value, lowerKey);
    }
  }
  return cleaned;
}

function scrubHttpResponseContext(value: unknown): Record<string, number> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const source = value as Record<string, unknown>;
  const safe: Record<string, number> = {};
  for (const field of ['status_code', 'body_size']) {
    const diagnostic = source[field];
    if (typeof diagnostic === 'number' && Number.isFinite(diagnostic)) safe[field] = diagnostic;
  }
  return safe;
}

function scrubStackLocals(value: unknown): void {
  if (!value || typeof value !== 'object') return;
  const stacktrace = value as { frames?: Array<Record<string, unknown>> };
  if (Array.isArray(stacktrace.frames)) {
    stacktrace.frames = stacktrace.frames.map((frame) => ({ ...frame, vars: {} }));
  }
}

function scrubSentryEvent(event: MutableSentryEvent): MutableSentryEvent {
  if (typeof event.message === 'string') event.message = '[REDACTED]';

  if (event.logentry) {
    if (event.logentry.message) event.logentry.message = '[REDACTED]';
    if (event.logentry.formatted) event.logentry.formatted = '[REDACTED]';
    if (event.logentry.params) event.logentry.params = [];
  }

  if (event.exception && Array.isArray(event.exception.values)) {
    event.exception.values = event.exception.values.map((exception) => {
      if (exception.value) exception.value = '[REDACTED]';
      scrubStackLocals(exception.stacktrace);
      return exception;
    });
  }

  if (event.threads && Array.isArray(event.threads.values)) {
    event.threads.values.forEach((thread) => scrubStackLocals(thread.stacktrace));
  }

  if (event.request) {
    event.request = scrubPIIFromObject(event.request) as Record<string, unknown>;
    if (event.request.data !== undefined) event.request.data = '[REDACTED]';
  }

  if (Array.isArray(event.breadcrumbs)) {
    event.breadcrumbs = event.breadcrumbs.map((breadcrumb) => ({
      ...breadcrumb,
      message: breadcrumb.message ? '[REDACTED]' : breadcrumb.message,
      data: scrubPIIFromObject(breadcrumb.data) as Record<string, unknown> | undefined,
    }));
  }

  if (event.extra) event.extra = scrubPIIFromObject(event.extra) as Record<string, unknown>;
  if (event.contexts) {
    event.contexts = scrubPIIFromObject(event.contexts, 'contexts') as Record<string, unknown>;
  }
  if (Array.isArray(event.spans)) {
    event.spans = event.spans.map((span) => ({
      ...span,
      description: typeof span.description === 'string'
        ? redactCredentialQueryParams(span.description)
        : span.description,
      data: scrubPIIFromObject(span.data) as Record<string, unknown> | undefined,
    }));
  }
  if (typeof event.transaction === 'string') {
    event.transaction = redactCredentialQueryParams(event.transaction);
  }

  const diagnosticCode = event.extra?.diagnostic_code;
  if (typeof diagnosticCode === 'string' && SAFE_AI_DIAGNOSTIC_CODES.has(diagnosticCode)) {
    const fingerprint = ['{{ default }}', diagnosticCode];
    for (const key of ['provider', 'error_type']) {
      const value = event.extra?.[key];
      if (typeof value === 'string' && /^[A-Za-z0-9_.-]{1,64}$/.test(value)) fingerprint.push(value);
    }
    event.fingerprint = fingerprint;
  }

  return event;
}

let isInitialized = false;

export function initSentry() {
  if (isInitialized) return;
  if (!SENTRY_DSN) {
    // eslint-disable-next-line no-console
    console.info('[sentry] VITE_SENTRY_DSN not set — Sentry disabled.');
    return;
  }

  Sentry.init({
    dsn: SENTRY_DSN,
    environment: SENTRY_ENV,
    release: import.meta.env.VITE_APP_VERSION || 'unknown',
    tracesSampleRate: SENTRY_TRACES_SAMPLE_RATE,
    // Drop errors from browser extensions / preview bots.
    denyUrls: [
      /extensions\//i,
      /^chrome:\/\//i,
      /^moz-extension:\/\//i,
    ],
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        // Disable session replay by default — replays can capture form
        // inputs which is a PII risk for a medical app. Enable only after
        // legal review and only for admin role.
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    beforeSend(event) {
      try {
        return scrubSentryEvent(event as unknown as MutableSentryEvent) as unknown as typeof event;
      } catch {
        // Drop an event if its privacy scrubber fails; never send it raw.
        return null;
      }
    },
    // Owner round-12 P1: pageload/navigation traces are NOT routed through
    // beforeSend — request.url carries the full URL (legacy ?token= handout
    // form) and http spans repeat it in span.description. Scrub the same
    // way regardless of trace sampling (errors are always sent, traces are
    // sampled — both must be credential-free).
    beforeSendTransaction(event) {
      try {
        return scrubSentryEvent(event as unknown as MutableSentryEvent) as unknown as typeof event;
      } catch {
        return null;
      }
    },
  });

  isInitialized = true;
}

export function captureException(error: unknown, context: Record<string, unknown>): void {
  if (!isInitialized) {
    // eslint-disable-next-line no-console
    console.error('[sentry-disabled]', error, context);
    return;
  }
  Sentry.captureException(error, { extra: context });
}

export function captureMessage(message: string, level: 'info' | 'warning' | 'error' | 'fatal' | 'debug' | 'log' = 'info'): void {
  if (!isInitialized) return;
  Sentry.captureMessage(message, level);
}

export { Sentry };
