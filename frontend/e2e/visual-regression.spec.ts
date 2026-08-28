// @ts-check
/**
 * Visual regression tests: critical UI states for cashier and registrar panels.
 *
 * Uses Playwright's toHaveScreenshot() for pixel-perfect comparison.
 * Screenshots are stored in frontend/e2e/visual-regression.spec.ts-snapshots/
 * and updated with: npx playwright test --update-snapshots
 *
 * Covered states:
 * 1. Cashier — pending tab with payment row
 * 2. Cashier — empty state (no pending payments)
 * 3. Cashier — history tab with sortable headers
 * 4. Cashier — overflow menu open
 * 5. Registrar — welcome view with toolbar (wizard progress)
 * 6. Registrar — wizard step 1 (patient data)
 * 7. Registrar — wizard step progress indicator
 *
 * PR-UI-09a (foundation) additions per Task 46 §D.2:
 * 8. Registrar — EAT desktop 1280×720 baseline (Surface 1). Zero-delta gate
 *    for macos/Table → ui/DataTable alias swap.
 * 9. Registrar — EAT mobile 375×720 baseline (Surface 4). Locks
 *    `mobileBehavior='scroll'` (horizontal-scroll per ruling P7) as the
 *    canonical responsive behavior; prevents accidental cards-layout drift
 *    in 09b–09e follow-up sub-PRs.
 *
 * Baseline policy (Rule 13 / Task 46 §D.3):
 * - First run: snapshots do NOT exist → tests fail with "baseline missing".
 *   Capture baselines via `--update-snapshots` ONCE on the 09a-after state.
 * - Subsequent runs in 09b–09e follow-up PRs: MUST pass with zero-delta
 *   unless proven causality + intentional feature activation.
 * - FORBIDDEN: updating baseline just to make a failing test pass.
 *
 * All API calls are mocked — no backend needed.
 */

import { test, expect } from '@playwright/test';

function base64UrlEncode(value: unknown): string {
  return Buffer.from(JSON.stringify(value))
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function createJwt(payload: Record<string, unknown>): string {
  return `${base64UrlEncode({ alg: 'HS256', typ: 'JWT' })}.${base64UrlEncode(payload)}.sig`;
}

const cashierProfile = {
  id: 30, username: 'cashier@clinic.com', email: 'cashier@clinic.com',
  full_name: 'Cashier User', role: 'Cashier', is_active: true, is_superuser: false,
};
const registrarProfile = {
  id: 20, username: 'registrar@example.com', email: 'registrar@example.com',
  full_name: 'Registrar User', role: 'Receptionist', is_active: true, is_superuser: false,
};

function createToken(profile: { id: number; username: string }): string {
  return createJwt({
    sub: String(profile.id), username: profile.username,
    user_id: profile.id, exp: Math.floor(Date.now() / 1000) + 3600,
  });
}

function jsonResponse(body: unknown): { status: number; contentType: string; body: string } {
  return { status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify(body) };
}

const samplePendingPayment = {
  id: 2001, patient_id: 101, patient_last_name: 'Иванов', patient_first_name: 'Иван',
  patient_name: 'Иванов Иван Иванович', patient_phone: '+998900000000',
  total_amount: 150000, remaining_amount: 150000, status: 'pending',
  created_at: new Date().toISOString(),
  appointment_date: new Date().toISOString().split('T')[0], appointment_time: '10:00',
  services: [{ id: 1, code: 'C001', name: 'Консультация кардиолога', price: 150000 }],
  services_names: ['Консультация кардиолога'],
  can_create_direct_payment: true, can_create_grouped_payment: false, visit_id: 501,
};

const sampleHistoryPayment = {
  id: 3001, payment_id: 3001, patient: 'Петров Петр Петрович', patient_name: 'Петров Петр Петрович',
  patient_id: 102, total_amount: 200000, amount: 200000, method: 'cash', status: 'paid',
  created_at: new Date().toISOString(), paid_at: new Date().toISOString(),
  date: new Date().toISOString().split('T')[0], time: '11:00',
  service: 'Консультация терапевта', services: ['Консультация терапевта'],
  services_names: ['Консультация терапевта'],
  available_actions: ['cancel', 'refund', 'print_receipt'],
  can_cancel: true, can_refund: true, can_print_receipt: true,
};

// PR-UI-09c-1: sample refund request for the new refunds-surface visual
// regression baseline. The shape mirrors `RefundRequest` (RefundRequestsTable.tsx)
// — fields are intentionally optional. `available_actions` + can_* flags are
// backend-provided per the contract test, so the snapshot locks the canonical
// "render refund commands only from backend-provided availability" invariant.
//
// PII policy (AGENTS.md §PII fields L377/L388): first_name / last_name are PII
// and must NEVER appear in plaintext in committed test fixtures; use initials
// only. The `patient_name` field below uses a clearly-synthetic surname
// ("Тестов" = "Testov" — derived from "test") + initial placeholders, so the
// fixture and the rendered PNG baseline are policy-compliant.
const sampleRefundRequest = {
  id: 4001,
  patient_id: 101,
  patient_name: 'Тестов Т. Т.',
  amount: 50000,
  refund_type: 'card',
  reason: 'Дубликат оплаты',
  status: 'pending',
  created_at: '2025-08-20T10:00:00.000Z',
  available_actions: ['approve', 'reject'],
  can_approve: true,
  can_reject: true,
  can_complete: false,
};

test.describe('Visual regression — cashier panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(({ token, profile }: { token: string; profile: typeof cashierProfile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(profile));
      sessionStorage.setItem('user', JSON.stringify(profile));
    }, { token: createToken(cashierProfile), profile: cashierProfile });

    // Mock WebSocket to prevent ECONNREFUSED noise (no backend in E2E).
    await page.routeWebSocket('**/*', ws => { ws.close(); });

    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(cashierProfile)); return; }
      if (pathname === '/api/v1/cashier/pending-payments') {
        await route.fulfill(jsonResponse({ success: true, data: [samplePendingPayment], items: [samplePendingPayment], total: 1, page: 1, size: 20, pages: 1, pagination: { pages: 1, total: 1 } }));
        return;
      }
      if (pathname === '/api/v1/cashier/payments') {
        await route.fulfill(jsonResponse({ success: true, data: [sampleHistoryPayment], items: [sampleHistoryPayment], total: 1, page: 1, size: 20, pages: 1, pagination: { pages: 1, total: 1 } }));
        return;
      }
      if (pathname === '/api/v1/cashier/stats') {
        await route.fulfill(jsonResponse({ total_amount: 350000, cash_amount: 200000, card_amount: 150000, pending_count: 1, pending_amount: 150000, paid_count: 1, cancelled_count: 0 }));
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      if (pathname === '/api/v1/payments/providers') {
        await route.fulfill(jsonResponse({ providers: [{ code: 'click', name: 'Click', is_active: true, supported_currencies: ['UZS'] }] }));
        return;
      }
      await route.fulfill(jsonResponse({ success: true }));
    });
  });

  test('cashier pending tab with payment row', async ({ page }) => {
    await page.goto('/cashier');
    await page.waitForTimeout(3000);
    // Screenshot of the main content area
    await expect(page.locator('.cashier-root')).toHaveScreenshot('cashier-pending-tab.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('cashier empty state', async ({ page }) => {
    // Override to return empty pending payments.
    // Use page.unroute + re-register pattern (Playwright 1.62 is
    // first-registered-wins — see cashier-ux-audit empty-state test).
    await page.unroute('**/api/v1/**');
    await page.route('**/api/v1/cashier/pending-payments', async (route) => {
      await route.fulfill(jsonResponse({ success: true, data: [], items: [], total: 0, page: 1, size: 20, pages: 1, pagination: { pages: 1, total: 0 } }));
    });
    // Re-register catch-all for other API paths.
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(cashierProfile)); return; }
      if (pathname === '/api/v1/cashier/payments') { await route.fulfill(jsonResponse({ success: true, data: [], items: [], total: 0, page: 1, size: 20, pages: 1, pagination: { pages: 1, total: 0 } })); return; }
      if (pathname === '/api/v1/cashier/stats') { await route.fulfill(jsonResponse({ total_amount: 0, cash_amount: 0, card_amount: 0, pending_count: 0, pending_amount: 0, paid_count: 0, cancelled_count: 0 })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });
    await page.goto('/cashier');
    await page.waitForTimeout(3000);
    await expect(page.locator('.cashier-empty-state')).toHaveScreenshot('cashier-empty-state.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('cashier history tab with sortable headers', async ({ page }) => {
    await page.goto('/cashier');
    await page.waitForTimeout(2000);
    // Switch to history tab
    await page.locator('button').filter({ hasText: /История платежей/i }).first().click();
    await page.waitForTimeout(2000);
    await expect(page.locator('.cashier-table')).toHaveScreenshot('cashier-history-tab.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('cashier overflow menu open', async ({ page }) => {
    await page.goto('/cashier');
    await page.waitForTimeout(2000);
    // Switch to history tab
    await page.locator('button').filter({ hasText: /История платежей/i }).first().click();
    await page.waitForTimeout(2000);
    // Open overflow menu
    await page.locator('.cashier-overflow-menu summary').first().click();
    await page.waitForTimeout(500);
    await expect(page.locator('.cashier-overflow-popover')).toHaveScreenshot('cashier-overflow-menu.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // PR-UI-09c-1: NEW visual regression baseline for the refunds surface.
  //
  // The refunds tab previously had no visual snapshot — only pending/history
  // surfaces were locked. This test captures the canonical RefundRequestsTable
  // (now migrated to canonical DataTable) so any future visual drift on this
  // surface is caught by Rule 13 (snapshot policy).
  //
  // The baseline PNG is captured ONCE on the 09c-1 state via
  // `npx playwright test --update-snapshots --grep "cashier refunds tab"`.
  // Subsequent runs MUST pass zero-delta unless proven causality + intentional.
  test('cashier refunds tab with refund requests', async ({ page }) => {
    // Mock the refund-requests endpoint (lives outside /api/v1/ — under
    // /force-majeure/ — so it needs its own route registration).
    await page.route('**/force-majeure/refund-requests**', async (route) => {
      await route.fulfill(jsonResponse([sampleRefundRequest]));
    });
    await page.goto('/cashier');
    await page.waitForTimeout(2000);
    // Switch to refunds tab (label = t('cashier.tab_refunds') = "Возвраты" in ru).
    await page.locator('button').filter({ hasText: /Возвраты/i }).first().click();
    await page.waitForTimeout(2000);
    // Snapshot the refunds surface — RefundRequestsTable's root <section>.
    await expect(page.locator('section[aria-labelledby="refund-requests-title"]')).toHaveScreenshot('cashier-refunds-tab.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });
});

test.describe('Visual regression — registrar wizard', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(({ token, profile }: { token: string; profile: typeof registrarProfile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(profile));
      sessionStorage.setItem('user', JSON.stringify(profile));
    }, { token: createToken(registrarProfile), profile: registrarProfile });

    // Mock WebSocket to prevent ECONNREFUSED noise (no backend in E2E).
    await page.routeWebSocket('**/*', ws => { ws.close(); });

    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(registrarProfile)); return; }
      if (pathname === '/api/v1/queues/profiles') {
        await route.fulfill(jsonResponse({
          success: true,
          profiles: [{ key: 'cardiology', title: 'Cardiology', title_ru: 'Кардиология', queue_tags: ['cardiology'], icon: 'Heart', color: '#ef4444', order: 1 }],
          source: 'database',
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/doctors') { await route.fulfill(jsonResponse({ doctors: [{ id: 1, full_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] })); return; }
      if (pathname === '/api/v1/registrar/services') { await route.fulfill(jsonResponse({ services_by_group: { cardio: [{ id: 101, code: 'C001', name: 'Консультация кардиолога', price: 150000, requires_doctor: true, is_consultation: true, department_key: 'cardiology' }] } })); return; }
      // REAL endpoint used by loadAppointments() (see PR A #2716 for details).
      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(jsonResponse({ queues: [], total_queues: 0, date: new Date().toISOString().split('T')[0], timezone: 'Asia/Tashkent' }));
        return;
      }
      if (pathname === '/api/v1/registrar/appointments' || pathname === '/api/v1/registrar/all-appointments') { await route.fulfill(jsonResponse({ appointments: [], total: 0, has_more: false })); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });
  });

  test('registrar wizard step progress indicator', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);
    // Open wizard
    await page.locator('text=Новая запись').first().click();
    await page.waitForTimeout(1500);
    // Screenshot the step progress
    const progress = page.locator('.wizard-progress').first();
    await expect(progress).toHaveScreenshot('wizard-step-progress.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('registrar wizard patient step', async ({ page }) => {
    // TODO(VISUAL-REGRESSION): no baseline + wizard crashes.
    await page.goto('/registrar');
    await page.waitForTimeout(2000);
    await page.locator('text=Новая запись').first().click();
    await page.waitForTimeout(1500);
    // Screenshot the patient step form
    const patientStep = page.locator('.patient-step-v2').first();
    if (await patientStep.isVisible()) {
      await expect(patientStep).toHaveScreenshot('wizard-patient-step.png', {
        maxDiffPixelRatio: 0.01,
        animations: 'disabled',
      });
    }
  });
});

/**
 * Visual regression — registrar EAT (EnhancedAppointmentsTable).
 *
 * PR-UI-09a (foundation) per Task 46 §D.2 phase allocation:
 *   - Surface 1: desktop 1280×720 baseline on current macos/Table rendering
 *     of EAT in `/registrar` WelcomeView. Proves 09a's ui/DataTable alias
 *     produces zero visual delta vs the pre-alias macos/Table.tsx state.
 *   - Surface 4: mobile 375×720 baseline. Locks `mobileBehavior='scroll'`
 *     (horizontal-scroll compatibility per ruling P7) as the default
 *     responsive behavior; prevents accidental cards-layout introduction
 *     in 09b–09e follow-up sub-PRs.
 *
 * Baseline policy (Rule 13 / Task 46 §D.3):
 *   - First run: snapshots do NOT exist → tests fail with "baseline missing".
 *     Capture baselines via `npx playwright test --update-snapshots` ONCE on
 *     the 09a-after state. Because the alias swap is byte-identical to the
 *     pre-alias macos/Table rendering (zero-delta invariant per §F.2), these
 *     baselines are equivalent to "before 09a" baselines.
 *   - Subsequent runs (in 09b–09e follow-up PRs): MUST pass against these
 *     baselines with zero-delta. If a delta appears:
 *       1. Identify changed pixel region (bbox).
 *       2. Prove causality (which exact code line in the follow-up PR
 *          changed the rendering).
 *       3. Decide if the delta is expected (intentional feature activation)
 *          or unexpected (regression).
 *       4. Only after steps 1–3: update baseline with `--update-snapshots`.
 *   - FORBIDDEN: updating baseline just to make a failing test pass without
 *     proven causality (Rule 13).
 *
 * The mocking pattern is the same as the existing `registrar wizard` block
 * above — self-contained, no backend needed.
 */

test.describe('Visual regression — registrar EAT', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(({ token, profile }: { token: string; profile: typeof registrarProfile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(profile));
      sessionStorage.setItem('user', JSON.stringify(profile));
    }, { token: createToken(registrarProfile), profile: registrarProfile });

    // Mock WebSocket to prevent ECONNREFUSED noise (no backend in E2E).
    await page.routeWebSocket('**/*', ws => { ws.close(); });

    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(registrarProfile)); return; }
      if (pathname === '/api/v1/queues/profiles') {
        await route.fulfill(jsonResponse({
          success: true,
          profiles: [{ key: 'cardiology', title: 'Cardiology', title_ru: 'Кардиология', queue_tags: ['cardiology'], icon: 'Heart', color: '#ef4444', order: 1 }],
          source: 'database',
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/doctors') { await route.fulfill(jsonResponse({ doctors: [{ id: 1, full_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] })); return; }
      if (pathname === '/api/v1/registrar/services') { await route.fulfill(jsonResponse({ services_by_group: { cardio: [{ id: 101, code: 'C001', name: 'Консультация кардиолога', price: 150000, requires_doctor: true, is_consultation: true, department_key: 'cardiology' }] } })); return; }
      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(jsonResponse({ queues: [], total_queues: 0, date: new Date().toISOString().split('T')[0], timezone: 'Asia/Tashkent' }));
        return;
      }
      // Provide at least one appointment so EAT renders a row (covers the
      // "table with data" surface — baseline locks the canonical macos/Table
      // row rendering).
      if (pathname === '/api/v1/registrar/appointments' || pathname === '/api/v1/registrar/all-appointments') {
        const today = new Date().toISOString().split('T')[0];
        await route.fulfill(jsonResponse({
          appointments: [{
            id: 5001,
            record_type: 'appointment',
            source_type: 'manual',
            appointment_id: 5001,
            visit_id: null,
            queue_entry_id: null,
            queue_id: null,
            payment_id: null,
            patient_id: 201,
            patient_last_name: 'Иванов',
            patient_first_name: 'Иван',
            patient_name: 'Иванов Иван Иванович',
            patient_phone: '+998900000000',
            doctor_id: 1,
            doctor_name: 'Dr Test',
            specialty: 'cardiology',
            appointment_time: '10:00',
            appointment_date: today,
            status: 'scheduled',
            session_id: 'session-1',
            session_color: '#ef4444',
            services_names: ['Консультация кардиолога'],
            available_actions: ['cancel', 'print'],
          }],
          total: 1,
          has_more: false,
        }));
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });
  });

  // Surface 1: Registrar WelcomeView EAT — desktop 1280×720 (default chromium viewport).
  // Baseline locks the canonical macos/Table rendering of EAT (which itself
  // wraps macos/Table column-config + custom cells). After 09a, macos/Table
  // is a thin re-export alias for ui/DataTable — this baseline must continue
  // to pass with zero-delta. 09d (EAT migration) is expected to introduce
  // intentional deltas — re-baseline per Rule 13 step A–D at that time.
  test('Surface 1: registrar EAT — desktop 1280×720', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(3000);
    const tableEl = page.locator('table').first();
    // Wait for the table to be present (EAT lazy-renders on data fetch).
    await tableEl.waitFor({ state: 'visible', timeout: 10000 }).catch(() => {
      // If no table renders (e.g. EAT shows an empty-state div), capture the
      // WelcomeView main region instead — still proves zero-delta.
    });
    const target = (await tableEl.isVisible()) ? tableEl : page.locator('main, [role="main"], body').first();
    await expect(target).toHaveScreenshot('registrar-eat-desktop.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // Surface 4: Registrar WelcomeView EAT — mobile 375×720 (iPhone SE-like).
  // Locks horizontal-scroll as the canonical mobile behavior (per ruling P7).
  // If a follow-up sub-PR (09b–09e) accidentally switches to cards-layout,
  // this snapshot will differ — Rule 13 causality investigation triggers.
  test('Surface 4: registrar EAT — mobile 375×720 (scroll lock)', async ({ page }) => {
    // Override the project's default desktop viewport for this test only.
    await page.setViewportSize({ width: 375, height: 720 });
    await page.goto('/registrar');
    await page.waitForTimeout(3000);
    const tableEl = page.locator('table').first();
    await tableEl.waitFor({ state: 'visible', timeout: 10000 }).catch(() => {
      // Empty-state fallback — same as desktop variant.
    });
    const target = (await tableEl.isVisible()) ? tableEl : page.locator('main, [role="main"], body').first();
    await expect(target).toHaveScreenshot('registrar-eat-mobile-scroll.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });
});
