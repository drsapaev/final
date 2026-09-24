// @ts-check
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

const PUBLIC_ROUTES = [
  { path: '/login', name: 'login' },
  { path: '/patient/login', name: 'patient login' },
  { path: '/patient/activate', name: 'patient activation' },
  { path: '/queue/join', name: 'queue join' },
  // PR 3390 review round: the PWA/SMS invitation deep link must render a
  // live public screen (was: wildcard -> /not-found). Without a token the
  // page shows the terminal invalid-link state without any API call.
  { path: '/confirm-visit', name: 'visit confirmation' },
  { path: '/payment/success', name: 'payment success callback' },
  { path: '/payment/cancel', name: 'payment cancel callback' },
];

const PROTECTED_ROUTES = [
  { path: '/admin', role: 'admin' },
  { path: '/registrar', role: 'registrar' },
  { path: '/doctor', role: 'doctor' },
  { path: '/lab', role: 'lab' },
];

async function clearAuthState(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
}

async function expectMountedApp(page: Page) {
  await expect(page.locator('#root')).toBeVisible();
  await expect.poll(
    async () => (await page.locator('body').innerText()).trim().length,
    { message: 'route should render non-empty body text' }
  ).toBeGreaterThan(0);
}

test.describe('Frontend 10/10 route smoke', () => {
  for (const route of PUBLIC_ROUTES) {
    test(`public route renders: ${route.name}`, async ({ page }) => {
      await clearAuthState(page);
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });

      await expectMountedApp(page);

      if (route.path === '/login') {
        await expect(page.locator('input[type="text"], input[name="username"]').first()).toBeVisible();
        await expect(page.locator('input[type="password"]').first()).toBeVisible();
      }
    });
  }

  for (const route of PROTECTED_ROUTES) {
    test(`protected route redirects without credentials: ${route.role}`, async ({ page }) => {
      test.info().annotations.push({
        type: 'credential-source',
        description: 'none; smoke validates unauthenticated route guard only',
      });

      await clearAuthState(page);
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });

      await expect(page).toHaveURL(/\/login$/);
      await expect(page.locator('input[type="text"], input[name="username"]').first()).toBeVisible();
      await expect(page.locator('input[type="password"]').first()).toBeVisible();
    });
  }
});

// ---------------------------------------------------------------------------
// PR 3390 review P1: split-origin visit-confirmation regression.
//
// The documented deployment model (ops/vps/frontend.env.sample) allows the
// frontend and the API on different origins via VITE_API_BASE_URL while the
// production backend keeps CSRF enabled. The backend CSRFMiddleware
// (double-submit cookie) requires BOTH the csrf_token cookie AND the
// X-CSRF-Token header on POSTs; a cross-origin XHR only carries the cookie
// when it is sent with withCredentials: true. The split-origin dev server is
// declared in playwright.config.ts (app on :5199, API base http://localhost:5999
// — same-site, cross-origin, like clinic.example.com vs api.clinic.example.com).
// This spec fails if either public POST of /confirm-visit loses credentials.
//
// Scope note (PR 3407 delta review P2): this regression proves the SAME-SITE
// cross-origin topology only. A true cross-SITE split (different registrable
// domains, CSRF_COOKIE_SAMESITE=none) additionally depends on the browser's
// third-party-cookie policy and is documented as best-effort, not guaranteed
// portable — see ops/vps/backend.env.sample.
// ---------------------------------------------------------------------------
const SPLIT_APP_ORIGIN = 'http://localhost:5199';
const SPLIT_API_ORIGIN = 'http://localhost:5999';
const SPLIT_CSRF_TOKEN = 'synthetic-split-origin-csrf-token';
const SPLIT_TOKEN = 'synthetic-split-origin-visit-token';

// Synthetic fixtures only (AGENTS.md policy): markers, no real identities.
const SPLIT_VISIT_CARD = {
  success: true,
  visit_id: 417,
  status: 'pending_confirmation',
  patient_name: 'Синтетик SYNTHETIC-Splitpatient',
  doctor_name: 'SYNTHETIC Split Doctor',
  visit_date: '2026-09-25',
  visit_time: '10:30',
  department: null,
  discount_mode: 'none',
  services: [
    { name: 'Приём SYNTHETIC-кардиолога', code: 'CARDIO', quantity: 1, price: 150000, total: 150000 },
  ],
  total_amount: 150000,
  currency: 'UZS',
  confirmation_expires_at: null,
};

const SPLIT_CONFIRMED = {
  success: true,
  message: 'Визит подтвержден (split-origin synthetic)',
  visit_id: 417,
  status: 'confirmed',
  patient_name: 'Синтетик SYNTHETIC-Splitpatient',
  visit_date: '2026-09-25',
  visit_time: '10:30',
  queue_numbers: [{ queue_tag: 'cardiology_common', number: 12, queue_id: 3 }],
  print_tickets: null,
};

type RecordedPost = { path: string; cookie: string; header: string };

test.describe('Split-origin visit confirmation (CSRF credentials regression)', () => {
  test('visit card and confirm POSTs carry the csrf cookie + header cross-origin', async ({ page }) => {
    await clearAuthState(page);
    // The invitation page runs on SPLIT_APP_ORIGIN while every API call goes
    // to SPLIT_API_ORIGIN. Seed the csrf_token cookie exactly like the
    // /auth/csrf-token bootstrap would (localhost cookies are port-agnostic,
    // so the cookie is in scope for the API origin).
    await page.context().addCookies([
      {
        name: 'csrf_token',
        value: SPLIT_CSRF_TOKEN,
        domain: 'localhost',
        path: '/',
        sameSite: 'Lax',
      },
    ]);

    const posts: RecordedPost[] = [];
    const corsHeaders = {
      'Access-Control-Allow-Origin': SPLIT_APP_ORIGIN,
      'Access-Control-Allow-Credentials': 'true',
      Vary: 'Origin',
    };

    await page.route(`${SPLIT_API_ORIGIN}/**`, async (route) => {
      const request = route.request();
      const headers = await request.allHeaders();

      if (request.method() === 'OPTIONS') {
        // CORS preflight for the JSON POST with custom X-CSRF-Token header.
        await route.fulfill({
          status: 204,
          headers: {
            ...corsHeaders,
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-CSRF-Token, Authorization',
            'Access-Control-Max-Age': '600',
          },
        });
        return;
      }

      const path = new URL(request.url()).pathname;
      if (request.method() === 'POST') {
        posts.push({
          path,
          cookie: headers['cookie'] ?? '',
          header: headers['x-csrf-token'] ?? '',
        });
      }

      // Mirror the backend CSRFMiddleware double-submit validation so the
      // page can only succeed when the browser actually attached the cookie.
      const cookieToken = /(?:^|;\s*)csrf_token=([^;]+)/.exec(headers['cookie'] ?? '')?.[1];
      const headerToken = headers['x-csrf-token'];
      const csrfOk = Boolean(cookieToken && headerToken && cookieToken === headerToken);
      const jsonHeaders = { ...corsHeaders, 'Content-Type': 'application/json' };

      if (path === '/api/v1/visits/info') {
        await route.fulfill(
          csrfOk
            ? { status: 200, headers: jsonHeaders, body: JSON.stringify(SPLIT_VISIT_CARD) }
            : {
                status: 403,
                headers: { ...jsonHeaders, 'X-CSRF-Status': 'rejected' },
                body: JSON.stringify({
                  detail: 'CSRF validation failed',
                  reason: cookieToken ? 'mismatch' : 'missing_cookie',
                }),
              },
        );
        return;
      }
      if (path === '/api/v1/patient/visits/confirm') {
        await route.fulfill(
          csrfOk
            ? { status: 200, headers: jsonHeaders, body: JSON.stringify(SPLIT_CONFIRMED) }
            : {
                status: 403,
                headers: { ...jsonHeaders, 'X-CSRF-Status': 'rejected' },
                body: JSON.stringify({
                  detail: 'CSRF validation failed',
                  reason: cookieToken ? 'mismatch' : 'missing_cookie',
                }),
              },
        );
        return;
      }
      if (path === '/api/v1/auth/csrf-token') {
        await route.fulfill({
          status: 200,
          headers: jsonHeaders,
          body: JSON.stringify({ csrf_token: SPLIT_CSRF_TOKEN }),
        });
        return;
      }
      await route.fulfill({
        status: 404,
        headers: jsonHeaders,
        body: JSON.stringify({ detail: `synthetic mock: no ${path}` }),
      });
    });

    await page.goto(`${SPLIT_APP_ORIGIN}/confirm-visit#token=${SPLIT_TOKEN}`, {
      waitUntil: 'domcontentloaded',
    });

    // The mocked split-origin API answers 200 only when the POST carried
    // BOTH the csrf cookie and the matching header — otherwise the page
    // would be stuck on the error state (403 is a retryable load failure).
    await expect(page.getByText('SYNTHETIC Split Doctor')).toBeVisible({ timeout: 15_000 });

    await page.getByRole('button', { name: 'Подтвердить визит' }).click();
    await expect(page.getByText('Визит подтвержден (split-origin synthetic)')).toBeVisible();

    const info = posts.find((p) => p.path === '/api/v1/visits/info');
    const confirm = posts.find((p) => p.path === '/api/v1/patient/visits/confirm');
    expect(info, 'POST /visits/info reached the API origin').toBeTruthy();
    expect(confirm, 'POST /patient/visits/confirm reached the API origin').toBeTruthy();
    // THE regression pin: with withCredentials the browser attaches the
    // csrf_token cookie to the cross-origin POSTs; without it the backend
    // CSRFMiddleware rejects with 403 missing_cookie.
    expect(info?.cookie, 'csrf cookie attached to /visits/info').toContain('csrf_token=');
    expect(confirm?.cookie, 'csrf cookie attached to /patient/visits/confirm').toContain('csrf_token=');
    expect(info?.header).toBe(SPLIT_CSRF_TOKEN);
    expect(confirm?.header).toBe(SPLIT_CSRF_TOKEN);
  });
});
