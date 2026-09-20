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
export function scrubPIIFromObject(obj: unknown): unknown {
  if (typeof obj === 'string') {
    return redactCredentialQueryParams(obj);
  }
  if (!obj || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(scrubPIIFromObject);

  const cleaned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.toLowerCase();
    if (MEDICAL_PII_KEYS.some((pii) => lowerKey.includes(pii))) {
      (cleaned as Record<string, unknown>)[key] = '[REDACTED]';
    } else {
      (cleaned as Record<string, unknown>)[key] = scrubPIIFromObject(value);
    }
  }
  return cleaned;
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
      // Scrub PII from request bodies, breadcrumbs, extra context, and contexts.
      // audit/phase-2, BS-57: previously `event.contexts` was not scrubbed,
      // so PII attached by Sentry SDK integrations (e.g., device context,
      // custom contexts set via Sentry.setContext()) leaked through.
      if (event.request) {
        event.request = scrubPIIFromObject(event.request) as typeof event.request;
      }
      if (event.breadcrumbs) {
        event.breadcrumbs = event.breadcrumbs.map((b) => ({
          ...b,
          data: scrubPIIFromObject(b.data) as Record<string, unknown> | undefined,
        }));
      }
      if (event.extra) {
        event.extra = scrubPIIFromObject(event.extra) as typeof event.extra;
      }
      if (event.contexts) {
        event.contexts = scrubPIIFromObject(event.contexts) as typeof event.contexts;
      }
      return event;
    },
    // Owner round-12 P1: pageload/navigation traces are NOT routed through
    // beforeSend — request.url carries the full URL (legacy ?token= handout
    // form) and http spans repeat it in span.description. Scrub the same
    // way regardless of trace sampling (errors are always sent, traces are
    // sampled — both must be credential-free).
    beforeSendTransaction(event) {
      if (event.request) {
        event.request = scrubPIIFromObject(event.request) as typeof event.request;
      }
      event.transaction = redactCredentialQueryParams(event.transaction);
      if (event.spans?.length) {
        event.spans = event.spans.map((span) => ({
          ...span,
          description:
            typeof span.description === 'string'
              ? redactCredentialQueryParams(span.description)
              : span.description,
          data: span.data
            ? (scrubPIIFromObject(span.data) as typeof span.data)
            : span.data,
        }));
      }
      return event;
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
