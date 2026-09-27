// @ts-check
/**
 * AI Safety Guardrails — regression tests for the medical AI safety contract.
 *
 * What this guards against:
 * - An AI endpoint silently dropping the root safety fields from its
 *   response (the `requires_doctor_confirmation: True` flag is the ONLY
 *   programmatic signal the frontend has that AI output is a suggestion,
 *   not a final record). If this flag goes missing, the frontend might
 *   auto-save AI output to the medical record — patient harm risk.
 * - An AI endpoint returning medical content WITHOUT the disclaimer.
 * - An AI endpoint returning content type that doesn't match the safety
 *   metadata (e.g. `requires_doctor_confirmation: False` on a diagnosis
 *   field — that should never happen).
 *
 * How this works:
 * - Logs in as a doctor user (QA_DOCTOR_USERNAME / QA_DOCTOR_PASSWORD).
 * - Calls each AI endpoint with a minimal valid payload.
 * - Asserts successful responses include root safety fields with
 *   requires_doctor_confirmation === true, or unavailable enhanced routes
 *   return an explicit 503 without medical content.
 * - Calls the same endpoint as a non-doctor (e.g. registrar) and asserts
 *   403 Forbidden — AI endpoints must be role-gated.
 *
 * This is a CONTRACT test — it does not validate the AI output itself,
 * only the safety envelope around it. AI quality is a separate concern
 * covered by evaluation pipelines.
 *
 * Run:
 *   QA_DOCTOR_USERNAME=doctor@clinic.com \
 *   QA_DOCTOR_PASSWORD=... \
 *   QA_REGISTRAR_USERNAME=registrar@clinic.com \
 *   QA_REGISTRAR_PASSWORD=... \
 *   npx playwright test e2e/ai-safety-guardrails.spec.ts
 */

import { test, expect } from '@playwright/test';
import type { APIRequestContext, APIResponse } from '@playwright/test';
import { createHmac } from 'crypto';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:18000';

const DOCTOR_USERNAME = process.env.QA_DOCTOR_USERNAME || 'doctor@clinic.com';
const DOCTOR_PASSWORD = process.env.QA_DOCTOR_PASSWORD;
const REGISTRAR_USERNAME = process.env.QA_REGISTRAR_USERNAME || 'registrar@clinic.com';
const REGISTRAR_PASSWORD = process.env.QA_REGISTRAR_PASSWORD;
const SMART_TEMPLATE_ENDPOINT = '/api/v1/emr/ai-enhanced/generate-smart-template?specialty=cardiology';
const SMART_SUGGESTIONS_ENDPOINT = '/api/v1/emr/ai-enhanced/smart-suggestions?field_name=complaints&specialty=cardiology';
const ANALYZE_COMPLAINTS_ENDPOINT = '/api/v1/ai/v2/analyze-complaints';
const COMPLAINTS_PAYLOAD = {
  complaint: 'Синтетическая жалоба для проверки контракта',
  specialty: 'cardiology',
};

/**
 * RFC 6238 TOTP (SHA1, 6 digits, 30s step) for the CI-seeded admin secret.
 * Implemented locally to avoid a new devDependency — must match pyotp
 * defaults used by the backend 2FA service.
 */
function base32Decode(input: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of input.replace(/=+$/, '').toUpperCase()) {
    const idx = alphabet.indexOf(ch);
    if (idx === -1) throw new Error(`Invalid base32 character: ${ch}`);
    bits += idx.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return Buffer.from(bytes);
}

function totpCode(secretBase32: string, atMs: number = Date.now()): string {
  const counter = Math.floor(atMs / 1000 / 30);
  const msg = Buffer.alloc(8);
  msg.writeUInt32BE(Math.floor(counter / 2 ** 32), 0);
  msg.writeUInt32BE(counter % 2 ** 32, 4);
  const digest = createHmac('sha1', base32Decode(secretBase32)).update(msg).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const code =
    ((digest[offset] & 0x7f) << 24) |
    (digest[offset + 1] << 16) |
    (digest[offset + 2] << 8) |
    digest[offset + 3];
  return (code % 1_000_000).toString().padStart(6, '0');
}

/**
 * Log in and return the access token. Throws if creds are missing.
 * Critical 2FA roles (Admin) get a TOTP challenge instead of tokens —
 * complete it via /2fa/verify using the CI-seeded secret.
 */
async function login(request: APIRequestContext, username: string, password: string | undefined, role: string): Promise<string> {
  if (!password) {
    throw new Error(`Set QA_${role.toUpperCase()}_PASSWORD to run AI safety tests.`);
  }
  const resp = await request.post(`${BACKEND_URL}/api/v1/authentication/login`, {
    data: { username, password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(resp.ok(), `login as ${role} should succeed`).toBeTruthy();
  const body = await resp.json();

  if (body.requires_2fa && body.pending_2fa_token) {
    const secret = process.env.QA_ADMIN_TOTP_SECRET;
    if (!secret) {
      throw new Error('Admin login hit a 2FA challenge — set QA_ADMIN_TOTP_SECRET (the secret seeded for the QA admin).');
    }
    const verify = await request.post(`${BACKEND_URL}/api/v1/2fa/verify`, {
      data: { pending_2fa_token: body.pending_2fa_token, totp_code: totpCode(secret) },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(verify.ok(), `2fa verify as ${role} should succeed`).toBeTruthy();
    const verified = await verify.json();
    if (!verified.access_token) {
      throw new Error(`2fa verify as ${role} returned no access_token: ${JSON.stringify(verified)}`);
    }
    return verified.access_token;
  }

  if (body.requires_2fa_setup && body.enrollment_token) {
    throw new Error(
      `login as ${role} hit 2FA enrollment — the QA admin must be seeded with an enrolled TOTP secret (see ai-safety-guardrails.yml seed step).`
    );
  }

  return body.access_token || body.token;
}

/**
 * Helper: call an AI endpoint with auth bearer token.
 */
async function callAiEndpoint(request: APIRequestContext, endpoint: string, payload: Record<string, unknown>, token: string) {
  return request.post(`${BACKEND_URL}${endpoint}`, {
    data: payload,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
}

/**
 * Assert that a response JSON contains the AI safety metadata block
 * with the required fields set correctly.
 */
interface SafetyMeta {
  requires_doctor_confirmation?: unknown;
  decision_boundary?: unknown;
  ai_notice?: unknown;
}

function expectSafetyMeta(body: SafetyMeta) {
  expect(body.requires_doctor_confirmation, 'root requires_doctor_confirmation must be true').toBe(true);
  expect(body.decision_boundary, 'root decision_boundary must be suggestion_only').toBe('suggestion_only');
  expect(typeof body.ai_notice, 'root ai_notice must be a string').toBe('string');
  expect((body.ai_notice as string).trim(), 'root ai_notice must not be empty').not.toBe('');
}

async function expectSafeOrUnavailable(resp: APIResponse) {
  expect([200, 503], `valid request returned unexpected status ${resp.status()}`).toContain(resp.status());
  const body = await resp.json();
  if (resp.status() === 503) {
    // The intentionally unavailable endpoint must not return any medical content.
    expect(body).toEqual({ detail: { error: 'ai_feature_unavailable' } });
    return;
  }
  expectSafetyMeta(body);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe.configure({ mode: 'serial' });

test.describe('AI Safety Guardrails', () => {
  let doctorToken!: string;
  let registrarToken: string | undefined;

  test.beforeAll(async ({ request }) => {
    doctorToken = await login(request, DOCTOR_USERNAME, DOCTOR_PASSWORD, 'doctor');
    if (REGISTRAR_PASSWORD) {
      registrarToken = await login(request, REGISTRAR_USERNAME, REGISTRAR_PASSWORD, 'registrar');
    }
  });

  test('EMR smart-template has a safety envelope or is explicitly unavailable', async ({ request }) => {
    const resp = await callAiEndpoint(
      request,
      SMART_TEMPLATE_ENDPOINT,
      {},
      doctorToken,
    );
    await expectSafeOrUnavailable(resp);
  });

  test('EMR smart-suggestions has a safety envelope or is explicitly unavailable', async ({ request }) => {
    const resp = await callAiEndpoint(
      request,
      SMART_SUGGESTIONS_ENDPOINT,
      {},
      doctorToken,
    );
    await expectSafeOrUnavailable(resp);
  });

  test('AI gateway analyze-complaints response is role-gated + safe', async ({ request }) => {
    const resp = await callAiEndpoint(
      request,
      ANALYZE_COMPLAINTS_ENDPOINT,
      COMPLAINTS_PAYLOAD,
      doctorToken,
    );

    expect(resp.status(), 'valid AI v2 request must reach the response contract').toBe(200);
    const body = await resp.json();
    expect(body.status, 'AI v2 probe must exercise a successful response').toBe('success');
    expectSafetyMeta(body);
  });

  test('non-doctor role cannot call AI endpoints (403)', async ({ request }) => {
    test.skip(!registrarToken, 'QA_REGISTRAR_PASSWORD not set — skipping role-gate test');

    const probes = [
      { endpoint: SMART_TEMPLATE_ENDPOINT, payload: {} },
      { endpoint: SMART_SUGGESTIONS_ENDPOINT, payload: {} },
      { endpoint: ANALYZE_COMPLAINTS_ENDPOINT, payload: COMPLAINTS_PAYLOAD },
      { endpoint: '/api/v1/ai/v2/suggest-icd10', payload: { symptoms: ['Синтетический симптом'] } },
    ];

    for (const { endpoint, payload } of probes) {
      // test.skip above guarantees registrarToken is set when the test runs.
      const resp = await callAiEndpoint(request, endpoint, payload, registrarToken!);
      expect(
        [401, 403].includes(resp.status()),
        `${endpoint} should reject registrar (got ${resp.status()})`,
      ).toBeTruthy();
    }
  });

  test('AI endpoints require authentication (401 without token)', async ({ request }) => {
    const probes = [
      { endpoint: SMART_TEMPLATE_ENDPOINT, payload: {} },
      { endpoint: ANALYZE_COMPLAINTS_ENDPOINT, payload: COMPLAINTS_PAYLOAD },
    ];

    for (const { endpoint, payload } of probes) {
      const resp = await request.post(`${BACKEND_URL}${endpoint}`, {
        data: payload,
        headers: { 'Content-Type': 'application/json' },
      });
      expect(
        [401, 403].includes(resp.status()),
        `${endpoint} should require auth (got ${resp.status()})`,
      ).toBeTruthy();
    }
  });
});

test.describe('AI Feature Flag Toggle (admin)', () => {
  test('disabling ai_smart_template returns 503 from endpoint', async ({ request }) => {
    // Skipped unless QA_ADMIN_PASSWORD is set — this test mutates state.
    const adminPw = process.env.QA_ADMIN_PASSWORD;
    test.skip(!adminPw, 'QA_ADMIN_PASSWORD not set');

    const adminToken = await login(
      request,
      process.env.QA_ADMIN_USERNAME || 'admin@clinic.com',
      adminPw,
      'admin',
    );

    const flagUrl = `${BACKEND_URL}/api/v1/admin/feature-flags/ai_smart_template`;
    const headers = { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' };
    const originalResp = await request.get(flagUrl, { headers });
    expect(originalResp.ok(), 'reading ai_smart_template before mutation should succeed').toBeTruthy();
    const originalFlag = await originalResp.json();
    expect(typeof originalFlag.enabled, 'flag enabled state must be boolean').toBe('boolean');
    const originallyEnabled: boolean = originalFlag.enabled;

    try {
      if (originallyEnabled) {
        const disableResp = await request.post(`${flagUrl}/toggle`, {
          data: { enabled: false, reason: 'e2e test' },
          headers,
        });
        expect(disableResp.ok(), 'toggle to disabled should succeed').toBeTruthy();
        const disabledFlag = await disableResp.json();
        expect(disabledFlag.enabled, 'toggle response must confirm disabled state').toBe(false);
      }

      // Verify the feature flag blocks a valid request before the route body runs.
      const doctorToken = await login(
        request,
        DOCTOR_USERNAME,
        DOCTOR_PASSWORD,
        'doctor',
      );
      const aiResp = await callAiEndpoint(
        request,
        SMART_TEMPLATE_ENDPOINT,
        {},
        doctorToken,
      );
      expect(aiResp.status(), 'disabled flag should yield 503').toBe(503);

      const body = await aiResp.json();
      expect(body.detail.error, 'error code should be feature_disabled').toBe('feature_disabled');
      expect(body.detail.flag, 'flag key should be in response').toBe('ai_smart_template');
    } finally {
      // Restore exactly the state observed before this test.
      if (originallyEnabled) {
        const restoreResp = await request.post(`${flagUrl}/toggle`, {
          data: { enabled: originallyEnabled, reason: 'e2e test cleanup' },
          headers,
        });
        expect(restoreResp.ok(), 'restoring original flag state should succeed').toBeTruthy();
        const restoredFlag = await restoreResp.json();
        expect(restoredFlag.enabled, 'restore response must match original flag state').toBe(originallyEnabled);
      }
    }
  });
});
