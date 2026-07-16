// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

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
 * `beforeSend`.
 */

import * as Sentry from '@sentry/react';

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
const SENTRY_ENV = import.meta.env.VITE_SENTRY_ENV || 'development';
const SENTRY_TRACES_SAMPLE_RATE = Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || 0.05);

const MEDICAL_PII_KEYS = [
  // Patient identifiers
  'iin', 'passport_number', 'passport_series', 'ssn', 'national_id',
  // Contact info
  'phone', 'phone_number', 'email',
  // Medical
  'diagnosis', 'diagnoses', 'icd10', 'icd10_codes', 'complaints',
  'examination', 'prescription', 'medications', 'allergies',
  // Visit
  'visit_reason', 'patient_name', 'patient_id', 'doctor_notes',
];

function scrubPIIFromObject(obj) {
  if (!obj || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(scrubPIIFromObject);

  const cleaned = {};
  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.toLowerCase();
    if (MEDICAL_PII_KEYS.some((pii) => lowerKey.includes(pii))) {
      cleaned[key] = '[REDACTED]';
    } else if (typeof value === 'object') {
      cleaned[key] = scrubPIIFromObject(value);
    } else {
      cleaned[key] = value;
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
      // Scrub PII from request bodies, breadcrumbs, extra context.
      if (event.request) {
        event.request = scrubPIIFromObject(event.request);
      }
      if (event.breadcrumbs) {
        event.breadcrumbs = event.breadcrumbs.map((b) => ({
          ...b,
          data: scrubPIIFromObject(b.data),
        }));
      }
      if (event.extra) {
        event.extra = scrubPIIFromObject(event.extra);
      }
      return event;
    },
  });

  isInitialized = true;
}

export function captureException(error, context) {
  if (!isInitialized) {
    // eslint-disable-next-line no-console
    console.error('[sentry-disabled]', error, context);
    return;
  }
  Sentry.captureException(error, { extra: context });
}

export function captureMessage(message, level = 'info') {
  if (!isInitialized) return;
  Sentry.captureMessage(message, level);
}

export { Sentry };
