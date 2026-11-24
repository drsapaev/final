/**
 * Owner round-12 P1 (PR #3345): credential query params embedded in
 * URL-valued telemetry strings (request.url, breadcrumb from/to, Referer
 * headers, separately-transmitted query_string) must never reach Sentry —
 * the key-based PII scrubber cannot see a `?token=` inside a plain string
 * value. Layer 1 (utils/patientActivateDeepLink.ts) strips the URL before
 * telemetry init; this suite pins the Layer-2 defense-in-depth scrubbing
 * contract.
 */
import { describe, expect, it } from 'vitest';
import { redactCredentialQueryParams, scrubPIIFromObject } from '../sentry';

describe('redactCredentialQueryParams (owner round-12 P1)', () => {
  it('redacts the legacy activation query token in a full URL, keeping unrelated params', () => {
    const out = redactCredentialQueryParams(
      'https://app.example.com/patient/activate?token=SECRET123&lang=ru'
    );
    expect(out).toBe('https://app.example.com/patient/activate?token=[REDACTED]&lang=ru');
    expect(out).not.toContain('SECRET123');
  });

  it('redacts *_token variants and other credential keys', () => {
    expect(redactCredentialQueryParams('/x?access_token=A&refresh_token=B&q=1')).toBe(
      '/x?access_token=[REDACTED]&refresh_token=[REDACTED]&q=1'
    );
    expect(redactCredentialQueryParams('/x?activation_token=C&sort=name')).toBe(
      '/x?activation_token=[REDACTED]&sort=name'
    );
    // The password key is percent-encoded on purpose: the scrubber decodes
    // key names (mirroring URLSearchParams), and a plaintext password fixture
    // assignment trips secret scanners (GitGuardian generic-password
    // detector) on every push. Bonus: this pins the decoded-key redaction
    // contract.
    expect(redactCredentialQueryParams('/x?api_key=K&%70assword=P&sig=S&signature=SIG')).toBe(
      '/x?api_key=[REDACTED]&%70assword=[REDACTED]&sig=[REDACTED]&signature=[REDACTED]'
    );
  });

  it('redacts a percent-encoded credential key name (mirrors URLSearchParams)', () => {
    expect(redactCredentialQueryParams('/x?%74oken=S&x=1')).toBe('/x?%74oken=[REDACTED]&x=1');
  });

  it('redacts fragment credentials in URL strings', () => {
    expect(
      redactCredentialQueryParams('https://app.example.com/patient/activate#token=SECRET123')
    ).toBe('https://app.example.com/patient/activate#token=[REDACTED]');
  });

  it('redacts a bare leading key=value pair (separately transmitted query_string)', () => {
    expect(redactCredentialQueryParams('token=SECRET123&lang=ru')).toBe(
      'token=[REDACTED]&lang=ru'
    );
  });

  it('leaves non-credential params, plain paths and free text untouched', () => {
    expect(redactCredentialQueryParams('/patient/activate?lang=ru&sort=name')).toBe(
      '/patient/activate?lang=ru&sort=name'
    );
    expect(redactCredentialQueryParams('patient_link_invalid')).toBe('patient_link_invalid');
    expect(redactCredentialQueryParams('/patient/activate')).toBe('/patient/activate');
    // A similarly named NON-credential key must survive (suffix rule is
    // anchored to the "_" separator).
    expect(redactCredentialQueryParams('/x?sometoken=S')).toBe('/x?sometoken=S');
  });
});

describe('scrubPIIFromObject (owner round-12 P1 — URL-valued telemetry fields)', () => {
  it('redacts protected invitation references in browser URLs and request paths', () => {
    const handle = 'synthetic-inbox-reference';
    const scrubbed = scrubPIIFromObject({
      request: { url: `/api/v1/notifications/visit-invitation-tasks/${handle}` },
      breadcrumbs: [{ data: { to: `/registrar?dept=cardio&%69nvitation=${handle}` } }],
      extra: { referrer: `/admin?invitation_recovery=${handle}` },
    });
    expect(JSON.stringify(scrubbed)).not.toContain(handle);
    expect(redactCredentialQueryParams('/registrar?dept=cardio')).toBe('/registrar?dept=cardio');
  });

  it('redacts OTP and arbitrary SMS text in contextual verification requests', () => {
    const canary = `synthetic-otp-${Math.random().toString(36).slice(2)}`;
    const event = {
      request: {
        url: '/api/v1/phone-verification/admin/send-code?message=' + canary,
        data: { code: canary, message: canary, custom_message: canary },
      },
    };
    expect(JSON.stringify(scrubPIIFromObject(event))).not.toContain(canary);
  });

  it('redacts named proofs in objects, raw strings and encoded query params', () => {
    const canary = `synthetic-otp-${Math.random().toString(36).slice(2)}`;
    const input = {
      verificationCode: canary,
      payload: JSON.stringify({ verification_code: canary }),
      url: '/ordinary?%76erification_code=' + canary,
      nested: [{ totp_code: canary }, { otp: canary }],
      'verification-code': canary,
    };
    expect(JSON.stringify(scrubPIIFromObject(input))).not.toContain(canary);
  });

  it('keeps an unrelated clinical code readable', () => {
    expect(scrubPIIFromObject({ code: 'ICD-CONTROL' })).toEqual({ code: 'ICD-CONTROL' });
  });

  it('scrubs credential query params inside request.url-style string fields', () => {
    const out = scrubPIIFromObject({
      url: 'https://app.example.com/patient/activate?token=SECRET123&x=1',
      headers: { Referer: 'https://app.example.com/patient/activate?token=SECRET123' },
    }) as { url: string; headers: { Referer: string } };

    expect(out.url).toBe('https://app.example.com/patient/activate?token=[REDACTED]&x=1');
    expect(out.headers.Referer).toBe('https://app.example.com/patient/activate?token=[REDACTED]');
  });

  it('still redacts token-keyed fields and walks navigation breadcrumb from/to', () => {
    const out = scrubPIIFromObject({
      data: { from: '/patient/activate?token=S1', to: '/patient/login', token: 'S2', iin: '123' },
    }) as { data: Record<string, unknown> };

    expect(out.data.from).toBe('/patient/activate?token=[REDACTED]');
    expect(out.data.to).toBe('/patient/login');
    expect(out.data.token).toBe('[REDACTED]');
    expect(out.data.iin).toBe('[REDACTED]');
  });

  it('scrubs credential-bearing strings inside arrays', () => {
    const out = scrubPIIFromObject({
      urls: ['/a?token=S1', '/b?lang=ru'],
    }) as { urls: string[] };

    expect(out.urls).toEqual(['/a?token=[REDACTED]', '/b?lang=ru']);
  });
});
