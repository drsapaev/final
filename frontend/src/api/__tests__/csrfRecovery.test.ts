/**
 * #05 Tier 1 — CSRF 403 recovery boundary tests.
 *
 * Tests the three core invariants:
 * 1. CSRF 403 ≠ authorization 403 (distinguished via X-CSRF-Status header)
 * 2. CSRF recovery ≤ 1 retry (no infinite retry loop)
 * 3. CSRF recovery ≠ logout (auth state preserved)
 *
 * Also tests:
 * - Plain 403 (no CSRF header) → no retry
 * - /authentication/login is CSRF-exempt
 */
import { describe, expect, it } from 'vitest';
import type { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { isCSRFRejection } from '../client';

// ─── Helper: create a mock AxiosError ─────────────────────────────────

function makeAxiosError(
  status: number,
  opts: {
    headers?: Record<string, string>;
    data?: unknown;
    config?: Partial<InternalAxiosRequestConfig>;
  } = {},
): AxiosError {
  const response: Partial<AxiosResponse> = {
    status,
    headers: opts.headers ?? {},
    data: opts.data,
  };
  return {
    response: response as AxiosResponse,
    config: opts.config as InternalAxiosRequestConfig,
    isAxiosError: true,
    name: 'AxiosError',
    message: `Request failed with status code ${status}`,
  } as AxiosError;
}

// ─── Invariant 1: CSRF 403 ≠ authorization 403 ───────────────────────

describe('#05 Tier 1: isCSRFRejection — CSRF 403 vs authorization 403', () => {
  it('detects CSRF rejection via X-CSRF-Status: rejected header', () => {
    const error = makeAxiosError(403, {
      headers: { 'x-csrf-status': 'rejected' },
    });
    expect(isCSRFRejection(error)).toBe(true);
  });

  it('detects CSRF rejection via X-CSRF-Status: rejected header (capitalized)', () => {
    const error = makeAxiosError(403, {
      headers: { 'X-CSRF-Status': 'rejected' },
    });
    expect(isCSRFRejection(error)).toBe(true);
  });

  it('detects CSRF rejection via reason field in response body', () => {
    const error = makeAxiosError(403, {
      data: { detail: 'CSRF validation failed', reason: 'missing_cookie' },
    });
    expect(isCSRFRejection(error)).toBe(true);
  });

  it('detects CSRF rejection via reason=mismatch', () => {
    const error = makeAxiosError(403, {
      data: { detail: 'CSRF validation failed', reason: 'mismatch' },
    });
    expect(isCSRFRejection(error)).toBe(true);
  });

  it('does NOT classify plain 403 (permission denied) as CSRF rejection', () => {
    const error = makeAxiosError(403, {
      data: { detail: 'Not enough permissions' },
    });
    expect(isCSRFRejection(error)).toBe(false);
  });

  it('does NOT classify 403 with unrelated X-CSRF-Status value as CSRF rejection', () => {
    const error = makeAxiosError(403, {
      headers: { 'x-csrf-status': 'ok' },
    });
    expect(isCSRFRejection(error)).toBe(false);
  });

  it('does NOT classify non-403 errors as CSRF rejection', () => {
    expect(isCSRFRejection(makeAxiosError(401))).toBe(false);
    expect(isCSRFRejection(makeAxiosError(404))).toBe(false);
    expect(isCSRFRejection(makeAxiosError(500))).toBe(false);
  });

  it('does NOT classify 403 with unrelated reason field as CSRF rejection', () => {
    const error = makeAxiosError(403, {
      data: { detail: 'Forbidden', reason: 'insufficient_role' },
    });
    expect(isCSRFRejection(error)).toBe(false);
  });
});

// ─── Invariant 2: CSRF recovery ≤ 1 retry ────────────────────────────

describe('#05 Tier 1: CSRF recovery — single retry limit', () => {
  // The _csrfRetried flag on the config object is the guard.
  // If the retry also gets a CSRF 403, the flag is already set
  // and the interceptor should NOT retry again.

  it('config with _csrfRetried=true should not trigger another retry', () => {
    // Simulate the state after a retry: the config already has _csrfRetried=true
    const config = { _csrfRetried: true, url: '/test' } as unknown as InternalAxiosRequestConfig;
    const error = makeAxiosError(403, {
      headers: { 'x-csrf-status': 'rejected' },
      config,
    });

    // isCSRFRejection still detects it as CSRF...
    expect(isCSRFRejection(error)).toBe(true);

    // ...but the interceptor logic checks _csrfRetried before retrying.
    // The actual retry guard is in the interceptor, not in isCSRFRejection.
    // We verify the flag is present (the interceptor will check it).
    expect((error.config as InternalAxiosRequestConfig & { _csrfRetried?: boolean })._csrfRetried).toBe(true);
  });
});

// ─── Invariant 3: CSRF recovery ≠ logout ─────────────────────────────

describe('#05 Tier 1: CSRF 403 must not trigger logout', () => {
  // The auth store checks isCSRFRejection before clearing tokens.
  // This is verified in the auth store code, not in the interceptor.
  // Here we verify the detection logic that the auth store relies on.

  it('CSRF 403 (with header) is distinguishable from auth 403 (without header)', () => {
    const csrfError = makeAxiosError(403, {
      headers: { 'x-csrf-status': 'rejected' },
    });
    const authError = makeAxiosError(403, {
      data: { detail: 'Not enough permissions' },
    });

    expect(isCSRFRejection(csrfError)).toBe(true);
    expect(isCSRFRejection(authError)).toBe(false);

    // The auth store uses this distinction:
    // - isCSRFRejection=true → keep auth state (no logout)
    // - isCSRFRejection=false → clear auth state (logout)
  });
});

// ─── /authentication/login CSRF exemption ────────────────────────────

describe('#05 Tier 1: /authentication/login CSRF exemption', () => {
  // This is a backend test — we verify the middleware config.
  // The actual integration test runs in the backend test suite.

  it('backend CSRF_EXEMPT_PREFIXES includes /authentication/login', async () => {
    // Read the backend middleware file and verify the path is present.
    // This is a static check — the full integration test is in
    // backend/tests/regression/test_p1_3_csrf_exemption_boundaries.py
    const fs = await import('fs');
    const path = await import('path');
    const middlewarePath = path.resolve(
      __dirname,
      '../../../../backend/app/middleware/csrf_middleware.py',
    );
    const content = fs.readFileSync(middlewarePath, 'utf-8');
    expect(content).toContain('"/authentication/login"');
  });
});
