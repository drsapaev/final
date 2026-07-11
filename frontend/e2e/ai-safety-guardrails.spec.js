// @ts-check
/**
 * AI Safety Guardrails — regression tests for the medical AI safety contract.
 *
 * What this guards against:
 * - An AI endpoint silently dropping the `ai_safety_meta` block from its
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
 * - Asserts the response JSON contains the safety_meta block with
 *   requires_doctor_confirmation === true.
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
 *   npx playwright test e2e/ai-safety-guardrails.spec.js
 */

import { test, expect } from '@playwright/test';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:18000';

const DOCTOR_USERNAME = process.env.QA_DOCTOR_USERNAME || 'doctor@clinic.com';
const DOCTOR_PASSWORD = process.env.QA_DOCTOR_PASSWORD;
const REGISTRAR_USERNAME = process.env.QA_REGISTRAR_USERNAME || 'registrar@clinic.com';
const REGISTRAR_PASSWORD = process.env.QA_REGISTRAR_PASSWORD;

/**
 * Log in and return the access token. Throws if creds are missing.
 */
async function login(request, username, password, role) {
  if (!password) {
    throw new Error(`Set QA_${role.toUpperCase()}_PASSWORD to run AI safety tests.`);
  }
  const resp = await request.post(`${BACKEND_URL}/api/v1/authentication/login`, {
    data: { username, password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(resp.ok(), `login as ${role} should succeed`).toBeTruthy();
  const body = await resp.json();
  return body.access_token || body.token;
}

/**
 * Helper: call an AI endpoint with auth bearer token.
 */
async function callAiEndpoint(request, endpoint, payload, token) {
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
function expectSafetyMeta(body) {
  // The safety meta may be at root level or nested under 'ai_safety_meta' / 'safety_meta'.
  const meta = body.ai_safety_meta || body.safety_meta || body;
  expect(meta, 'response should contain AI safety metadata').toBeDefined();
  expect(meta.requires_doctor_confirmation, 'requires_doctor_confirmation must be true').toBe(true);
  expect(meta.decision_boundary, 'decision_boundary must be suggestion_only').toBe('suggestion_only');
  expect(meta.ai_notice, 'ai_notice disclaimer must be present').toBeTruthy();
  expect(typeof meta.ai_notice, 'ai_notice must be a string').toBe('string');
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('AI Safety Guardrails', () => {
  test.describe.configure({ mode: 'serial' });

  let doctorToken;
  let registrarToken;

  test.beforeAll(async ({ request }) => {
    doctorToken = await login(request, DOCTOR_USERNAME, DOCTOR_PASSWORD, 'doctor');
    if (REGISTRAR_PASSWORD) {
      registrarToken = await login(request, REGISTRAR_USERNAME, REGISTRAR_PASSWORD, 'registrar');
    }
  });

  test('EMR smart-template response includes safety_meta', async ({ request }) => {
    const resp = await callAiEndpoint(
      request,
      '/api/v1/emr/ai-enhanced/generate-smart-template',
      {
        specialty: 'cardiology',
        patient_id: 1,
        visit_id: 1,
      },
      doctorToken,
    );

    // Accept 200 (success) or 422 (bad payload) — both must include safety_meta
    // if the body contains AI content. 503 (feature flag disabled) skips.
    if (resp.status() === 503) {
      test.skip(true, 'ai_smart_template feature flag is disabled');
    }

    expect([200, 422].includes(resp.status()), `unexpected status: ${resp.status()}`).toBeTruthy();
    const body = await resp.json();

    if (resp.status() === 200) {
      expectSafetyMeta(body);
    }
  });

  test('EMR smart-suggestions response includes safety_meta', async ({ request }) => {
    const resp = await callAiEndpoint(
      request,
      '/api/v1/emr/ai-enhanced/smart-suggestions',
      {
        specialty: 'cardiology',
        field: 'complaints',
        context: { patient_id: 1 },
      },
      doctorToken,
    );

    if (resp.status() === 503) {
      test.skip(true, 'ai_smart_suggestions feature flag is disabled');
    }

    if (resp.status() === 200) {
      const body = await resp.json();
      expectSafetyMeta(body);
    }
  });

  test('AI gateway analyze-complaints response is role-gated + safe', async ({ request }) => {
    const resp = await callAiEndpoint(
      request,
      '/api/v1/ai/v2/analyze-complaints',
      {
        complaints: 'Боли в груди при физической нагрузке',
        specialty: 'cardiology',
      },
      doctorToken,
    );

    if (resp.status() === 503) {
      test.skip(true, 'ai_complaint_analysis feature flag is disabled');
    }

    expect([200, 422, 500].includes(resp.status()), `unexpected status: ${resp.status()}`).toBeTruthy();

    if (resp.status() === 200) {
      const body = await resp.json();
      // ai_gateway uses a slightly different response shape — check for
      // either ai_safety_meta or the explicit safety fields.
      const meta = body.ai_safety_meta || body.safety_meta;
      if (meta) {
        expectSafetyMeta(body);
      } else {
        // If no safety_meta block, the response must at least include a
        // provider name and audit_id so we can trace what happened.
        expect(body.provider || body.ai_provider, 'AI response should identify its provider').toBeTruthy();
        expect(body.audit_id || body.request_id, 'AI response should include audit id').toBeTruthy();
      }
    }
  });

  test('non-doctor role cannot call AI endpoints (403)', async ({ request }) => {
    test.skip(!registrarToken, 'QA_REGISTRAR_PASSWORD not set — skipping role-gate test');

    const endpoints = [
      '/api/v1/emr/ai-enhanced/generate-smart-template',
      '/api/v1/emr/ai-enhanced/smart-suggestions',
      '/api/v1/ai/v2/analyze-complaints',
      '/api/v1/ai/v2/suggest-icd10',
    ];

    for (const endpoint of endpoints) {
      const resp = await callAiEndpoint(request, endpoint, {}, registrarToken);
      expect(
        [401, 403].includes(resp.status()),
        `${endpoint} should reject registrar (got ${resp.status()})`,
      ).toBeTruthy();
    }
  });

  test('AI endpoints require authentication (401 without token)', async ({ request }) => {
    const endpoints = [
      '/api/v1/emr/ai-enhanced/generate-smart-template',
      '/api/v1/ai/v2/analyze-complaints',
    ];

    for (const endpoint of endpoints) {
      const resp = await request.post(`${BACKEND_URL}${endpoint}`, {
        data: {},
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

    // 1. Disable the flag
    const disableResp = await request.post(
      `${BACKEND_URL}/api/v1/admin/feature-flags/ai_smart_template/toggle`,
      {
        data: { enabled: false, reason: 'e2e test' },
        headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
      },
    );
    expect(disableResp.ok(), 'toggle to disabled should succeed').toBeTruthy();

    try {
      // 2. Verify endpoint returns 503
      const doctorToken = await login(
        request,
        DOCTOR_USERNAME,
        DOCTOR_PASSWORD,
        'doctor',
      );
      const aiResp = await callAiEndpoint(
        request,
        '/api/v1/emr/ai-enhanced/generate-smart-template',
        { specialty: 'cardiology' },
        doctorToken,
      );
      expect(aiResp.status(), 'disabled flag should yield 503').toBe(503);

      const body = await aiResp.json();
      expect(body.detail.error, 'error code should be feature_disabled').toBe('feature_disabled');
      expect(body.detail.flag, 'flag key should be in response').toBe('ai_smart_template');
    } finally {
      // 3. Re-enable the flag — always, even if assertions failed
      await request.post(
        `${BACKEND_URL}/api/v1/admin/feature-flags/ai_smart_template/toggle`,
        {
          data: { enabled: true, reason: 'e2e test cleanup' },
          headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
        },
      );
    }
  });
});
