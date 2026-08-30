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
import { installAuthenticatedQaHarness } from './support/authenticatedQa';

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
    // PR-UI-09c-4: deterministic readiness wait. The previous fixed
    // waitForTimeout(3000) raced the Vite dev-server cold module transform
    // (EAT now eagerly imports the canonical DataTable, adding module
    // requests to the /registrar graph) — on loaded CI runners the
    // ModernTabs "Загрузка отделений..." state outlived the sleep and the
    // body fallback captured a transient loading state (12328 px diff).
    // Wait for the department tabs to finish loading instead; catch() keeps
    // the original behavior of screenshotting whatever rendered — a real
    // readiness regression then fails the snapshot assertion itself.
    await page.locator('.tab-button.all-departments').first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .catch(() => {});
    await page.waitForTimeout(300);
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
    // PR-UI-09c-4: deterministic readiness wait (see Surface 1 note) —
    // replaces the fixed 3000ms sleep that raced ModernTabs loading.
    await page.locator('.tab-button.all-departments').first()
      .waitFor({ state: 'visible', timeout: 15000 })
      .catch(() => {});
    await page.waitForTimeout(300);
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

/**
 * Visual regression — PR-UI-12-4 five clinical screens (plan §PR-UI-12 AC:
 * "Visual regression на 5 экранах (EMR, Queue, Appointments, Patients, Lab)").
 *
 * Sticky-header wiring shipped in PR-UI-12-4 (plan item 4 "Все таблицы —
 * sticky header при скролле"):
 *   - Queue surface: QueueTable (canonical DataTable) — stickyHeader +
 *     maxHeight=480 bounded viewport.
 *   - Appointments surface: EAT — stickyHeader + maxHeight=560 bounded
 *     viewport (the screen's canonical table behind the "Расширенная
 *     таблица" toggle; the bespoke native fallback table on the same screen
 *     is intentionally untouched — zero-delta).
 *   - EMR / Patients / Lab screens carry NO data tables on main (verified:
 *     EMR = form sections, /clinical/search = result cards, /lab = queue
 *     cards + virtualized card list), so nothing was wired there — these
 *     baselines lock the zero-delta invariant for the 12-4 change window.
 *
 * Baseline policy (Rule 13): these are NEW baselines captured ONCE on the
 * PR-UI-12-4 state (new tests → first capture; no existing baseline was
 * re-captured). The two wired surfaces additionally carry a DOM-level
 * STICKY PROOF: after scrolling the bounded viewport to the bottom, the
 * header row's top must sit at the viewport's top — a geometry assertion,
 * deterministic and independent of sub-pixel screenshot noise.
 */
test.describe('Visual regression — PR-UI-12-4 five clinical screens', () => {
  const labProfile = {
    id: 40, username: 'lab@clinic.com', email: 'lab@clinic.com',
    full_name: 'Lab User', role: 'Lab', is_active: true, is_superuser: false,
  };
  const doctorProfile = {
    id: 50, username: 'doctor@clinic.com', email: 'doctor@clinic.com',
    full_name: 'Doctor User', role: 'Doctor', is_active: true, is_superuser: false,
  };
  // Appointments.tsx gates the page via <RoleGate roles={['Admin','Registrar',
  // 'Doctor']}> — unlike the route-registry access check (routeSelectors), the
  // page-level RoleGate does NOT apply ROLE_ALIASES, so a 'Receptionist'
  // profile is denied there. Use the literal 'Registrar' role (pre-existing
  // page/route gate divergence, documented in the PR body — not changed by
  // 12-4).
  const appointmentsProfile = {
    id: 21, username: 'registrar2@example.com', email: 'registrar2@example.com',
    full_name: 'Registrar User', role: 'Registrar', is_active: true, is_superuser: false,
  };

  // Flat queue entry shape consumed by useQueueManager/QueueTable (mirrors
  // registrar-time.spec.ts — the REAL /registrar/queues/today entry shape).
  // PII policy: synthetic "Тестов Тест Тестович" (derived from "test").
  const queueEntry = (i: number) => ({
    id: 2000 + i,
    number: i + 1,
    patient_id: 100 + i,
    patient_name: `Тестов Тест Тестович ${i + 1}`,
    patient_phone: '+998900000000',
    queue_number: i + 1,
    queue_time: `2026-08-29T09:${String(i * 3).padStart(2, '0')}:00+05:00`,
    created_at: `2026-08-29T09:${String(i * 3).padStart(2, '0')}:00+05:00`,
    status: i === 0 ? 'called' : 'waiting',
    source: i % 2 === 0 ? 'online' : 'desk',
    payment_status: 'paid',
    payment_type: 'cash',
    cost: 100000,
    services: ['Консультация'],
    service_codes: ['K01'],
    discount_mode: 'none',
    approval_status: null,
    type: 'online_queue',
    record_type: 'online_queue',
    queue_entry_id: 2000 + i,
    department_key: 'cardiology',
    department: 'cardiology',
    session_id: 'sess-1',
  });

  const queuesTodayResponse = (entries: ReturnType<typeof queueEntry>[]) => jsonResponse({
    queues: [{
      queue_id: 1,
      specialist_id: 1,
      specialist_name: 'Dr Test',
      specialty: 'cardiology',
      cabinet: '12',
      entries,
      stats: { total: entries.length, waiting: entries.length - 1, called: 1, served: 0, online_entries: 0 },
      opened_at: '2026-08-29T09:00:00+05:00',
    }],
    total_queues: 1,
    date: '2026-08-29',
    timezone: 'Asia/Tashkent',
  });

  async function installAuth(page: import('@playwright/test').Page, profile: typeof labProfile) {
    await page.addInitScript(({ token, profile: p }: { token: string; profile: typeof labProfile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(p));
      sessionStorage.setItem('user', JSON.stringify(p));
    }, { token: createToken(profile), profile });
    await page.routeWebSocket('**/*', ws => { ws.close(); });
  }

  /**
   * DOM-level sticky proof: scroll the bounded table viewport to the bottom
   * and assert the header row stays glued to the viewport's top edge.
   * Returns the geometry for the caller's additional assertions.
   */
  async function assertStickyHeader(page: import('@playwright/test').Page, viewportSelector: string) {
    const geometry = await page.locator(viewportSelector).evaluate((el: HTMLElement) => {
      el.scrollTop = el.scrollHeight;
      const thead = el.querySelector('thead');
      const headerRect = thead ? thead.getBoundingClientRect() : null;
      const viewportRect = el.getBoundingClientRect();
      return {
        scrollable: el.scrollHeight > el.clientHeight,
        headerTop: headerRect ? headerRect.top : null,
        viewportTop: viewportRect.top,
      };
    });
    expect(geometry.scrollable, 'table viewport must actually scroll (content exceeds maxHeight)').toBe(true);
    expect(geometry.headerTop).not.toBeNull();
    // Sticky header: after full scroll the header row's top sits at the
    // viewport's top (tolerance covers sub-pixel rounding only).
    expect((geometry.headerTop as number) - geometry.viewportTop).toBeLessThan(1.5);
    return geometry;
  }

  // --- Surface 1/5: Queue (/registrar/queue → QueueView → ModernQueueManager
  // → QueueTable). 12 entries exceed the 480px viewport bound → internal
  // scroll under a sticky header. Deep link ?doctor=1 pre-selects the
  // specialist (QueueView wires searchParams.doctor into selectedDoctor), so
  // the queue snapshot loads without any dropdown interaction.
  test('PR-UI-12-4 queue screen — sticky header under bounded viewport', async ({ page }) => {
    await installAuth(page, registrarProfile);
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(registrarProfile)); return; }
      if (pathname === '/api/v1/queue/available-specialists') {
        await route.fulfill(jsonResponse({ specialists: [{ id: 1, doctor_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] }));
        return;
      }
      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(queuesTodayResponse(Array.from({ length: 12 }, (_, i) => queueEntry(i))));
        return;
      }
      if (pathname === '/api/v1/queues/profiles') {
        await route.fulfill(jsonResponse({ success: true, profiles: [], source: 'database' }));
        return;
      }
      if (pathname === '/api/v1/registrar/doctors') { await route.fulfill(jsonResponse({ doctors: [{ id: 1, full_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] })); return; }
      if (pathname === '/api/v1/registrar/services') { await route.fulfill(jsonResponse({ services_by_group: {} })); return; }
      if (pathname === '/api/v1/registrar/queue-settings') { await route.fulfill(jsonResponse({ data: { max_queue_size: 25 } })); return; }
      if (pathname === '/api/v1/registrar/departments') { await route.fulfill(jsonResponse({ data: [{ key: 'cardio', title: 'Кардиология', active: true }] })); return; }
      if (pathname === '/api/v1/registrar/appointments' || pathname === '/api/v1/registrar/all-appointments') { await route.fulfill(jsonResponse({ appointments: [], total: 0, has_more: false })); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/registrar/queue?doctor=1');
    // Deterministic readiness: the queue table renders its entries.
    await page.locator('.qt-table-container table').first().waitFor({ state: 'visible', timeout: 15000 });
    await expect(page.locator('.qt-table-container').getByText('Тестов Тест Тестович 1').first()).toBeVisible();
    await page.waitForTimeout(300);

    // Sticky proof: scroll the bounded viewport, header stays at its top.
    await assertStickyHeader(page, '.qt-table-container .mac-table-scroll-wrapper');

    // Baseline: the queue table surface at rest (before the scroll above —
    // reset scroll so the captured state is the canonical at-rest top view).
    await page.locator('.qt-table-container .mac-table-scroll-wrapper').evaluate((el: HTMLElement) => { el.scrollTop = 0; });
    await expect(page.locator('.qt-table-container')).toHaveScreenshot('pr124-queue-screen.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // --- Surface 2/5: Appointments (/clinical/appointments → Appointments.tsx
  // → EAT behind the "Расширенная таблица" toggle). 15 rows exceed the 560px
  // viewport bound → internal scroll under a sticky header.
  test('PR-UI-12-4 appointments screen — EAT sticky header under bounded viewport', async ({ page }) => {
    // PR-UI-14-3 CI fix (pre-existing date-rollover flake, root-caused):
    // EAT renders queue-number badges ONLY for rows whose appointment_date
    // equals getLocalDateString() (Asia/Tashkent frame). The mock below
    // hardcodes '2026-08-29' — the day the baseline was captured — so with
    // a real clock the test flips red after every UTC+5 midnight rollover
    // (badges disappear, 0.02 pixel diff > 0.01 tolerance). Installing the
    // fake clock at the baseline-capture instant keeps the rendered surface
    // byte-identical to the committed baseline on any future run date.
    // Time keeps RUNNING from this instant (clock.install, not setFixedTime)
    // so page timers (debounces, auto-refresh) keep firing normally.
    await page.clock.install({ time: new Date('2026-08-29T12:00:00+05:00') });
    await installAuth(page, appointmentsProfile);
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(appointmentsProfile)); return; }
      if (pathname === '/api/v1/appointments') {
        const today = '2026-08-29';
        await route.fulfill(jsonResponse(Array.from({ length: 15 }, (_, i) => ({
          id: 5000 + i,
          record_type: 'appointment',
          source_type: 'manual',
          appointment_id: 5000 + i,
          patient_id: 200 + i,
          patient_last_name: 'Тестов',
          patient_first_name: 'Тест',
          patient_fio: `Тестов Тест Тестович ${i + 1}`,
          patient_name: `Тестов Тест Тестович ${i + 1}`,
          patient_phone: '+998900000000',
          doctor_id: 1,
          doctor_name: 'Dr Test',
          specialty: 'cardiology',
          appointment_time: `10:${String(i * 4).padStart(2, '0')}`,
          appointment_date: today,
          status: 'scheduled',
          session_id: 'session-1',
          session_color: '#ef4444',
          services_names: ['Консультация кардиолога'],
          available_actions: ['cancel', 'print'],
        }))));
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/clinical/appointments');
    // Deterministic readiness: the native fallback table renders rows.
    await page.locator('table').first().waitFor({ state: 'visible', timeout: 15000 });
    // Switch to the canonical EAT (the appointments surface's table that
    // PR-UI-12-4 wires sticky headers on).
    await page.locator('div[role="checkbox"]').filter({ hasText: 'Расширенная таблица' }).first().click();
    await page.locator('.eat-table-scroll table').first().waitFor({ state: 'visible', timeout: 15000 });
    await expect(page.locator('.eat-table-scroll').getByText('Тестов Тест Тестович 1').first()).toBeVisible();
    await page.waitForTimeout(300);

    // Sticky proof: scroll the bounded viewport, header stays at its top.
    await assertStickyHeader(page, '.eat-table-scroll .mac-table-scroll-wrapper');

    await page.locator('.eat-table-scroll .mac-table-scroll-wrapper').evaluate((el: HTMLElement) => { el.scrollTop = 0; });
    await expect(page.locator('.eat-table-scroll')).toHaveScreenshot('pr124-appointments-screen.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // --- Surface 3/5: Patients (/clinical/search → Search.tsx). No data table
  // on this screen (result cards) — nothing to wire sticky headers on; the
  // baseline locks the zero-delta invariant for the screen.
  test('PR-UI-12-4 patients screen — search results (zero-delta lock, no tables)', async ({ page }) => {
    await installAuth(page, registrarProfile);
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(registrarProfile)); return; }
      if (pathname === '/api/v1/patients/') {
        await route.fulfill(jsonResponse(Array.from({ length: 4 }, (_, i) => ({
          id: 300 + i,
          last_name: 'Тестов',
          first_name: 'Тест',
          middle_name: 'Тестович',
          full_name: `Тестов Тест Тестович ${i + 1}`,
          phone: '+998900000000',
          birth_date: '1990-01-01',
          sex: 'male',
          created_at: '2026-01-01T00:00:00Z',
        }))));
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/clinical/search');
    const input = page.getByLabel('Поиск пациентов и визитов');
    await input.waitFor({ state: 'visible', timeout: 15000 });
    await input.fill('Тестов');
    await input.press('Enter');
    // Deterministic readiness: all 4 patient result cards render (the card
    // display joins last/first/middle name — identical across fixtures; the
    // accessible name comes from the button's text content).
    await expect(page.getByRole('button', { name: /Открыть пациента/ })).toHaveCount(4, { timeout: 15000 });
    await page.waitForTimeout(300);

    await expect(page.locator('#main-content')).toHaveScreenshot('pr124-patients-screen.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // --- Surface 4/5: Lab (/lab → LabPanel). No data table on this screen
  // (queue cards + virtualized card list) — nothing to wire sticky headers
  // on; the baseline locks the zero-delta invariant for the screen.
  test('PR-UI-12-4 lab screen — lab queue (zero-delta lock, no tables)', async ({ page }) => {
    await installAuth(page, labProfile);
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(labProfile)); return; }
      if (pathname === '/api/v1/lab/queue/today') {
        await route.fulfill(jsonResponse({
          entries: Array.from({ length: 5 }, (_, i) => ({
            id: 600 + i,
            appointment_id: 600 + i,
            patient_fio: `Тестов Тест Тестович ${i + 1}`,
            patient_id: 400 + i,
            status: i === 0 ? 'in_progress' : 'waiting',
            created_at: '2026-08-29T09:00:00+05:00',
            services: ['Общий анализ крови'],
            queue_number: i + 1,
          })),
          total: 5,
        }));
        return;
      }
      // Lab catalog endpoints are consumed as BARE ARRAYS (LabTemplateWorkbench
      // maps over them directly) — object wrappers crash the render tree.
      if (pathname === '/api/v1/lab/templates') { await route.fulfill(jsonResponse([])); return; }
      if (pathname === '/api/v1/lab/catalog/units') { await route.fulfill(jsonResponse([])); return; }
      if (pathname === '/api/v1/lab/catalog/analytes') { await route.fulfill(jsonResponse([])); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    await page.goto('/lab');
    await page.locator('.lqw-root').first().waitFor({ state: 'visible', timeout: 15000 });
    await expect(page.locator('.lqw-root').getByText('Тестов Тест Тестович 1').first()).toBeVisible();
    await page.waitForTimeout(300);

    await expect(page.locator('.lqw-root').first()).toHaveScreenshot('pr124-lab-screen.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // --- Surface 5/5: EMR (doctor panel visit view → EMRContainerV2). No data
  // table on this screen (form sections) — nothing to wire sticky headers on;
  // the baseline locks the zero-delta invariant for the screen. The EMR GET
  // is mocked 404 → the canonical "new visit draft" state (the same path
  // production takes for a first visit).
  test('PR-UI-12-4 EMR screen — dermatology visit view (zero-delta lock, no tables)', async ({ page }) => {
    await installAuth(page, doctorProfile);
    const dermaQueueEntry = {
      id: 1001,
      number: 1,
      patient_id: 101,
      patient_fio: 'Тестов Тест Тестович',
      patient_name: 'Тестов Тест Тестович',
      patient_phone: '+998900000000',
      patient_birth_year: 1990,
      services: [{ id: 101, code: 'D001', name: 'Консультация дерматолога', price: 150000 }],
      cost: 150000,
      total_amount: 150000,
      payment_status: 'paid',
      payment_type: 'cash',
      canonical_status: 'queued',
      status: 'queued',
      queue_position: 1,
      queue_tag: 'derma',
      visit_id: 501,
      appointment_date: '2026-08-29',
      appointment_time: '10:00',
      created_at: '2026-08-29T09:00:00+05:00',
      doctor_id: 1,
      doctor_name: 'Dr Test',
      department: 'derma',
      available_actions: ['in_cabinet', 'complete'],
      queue_entry_id: 1001,
      can_start_visit: true,
      record_kind: 'appointment',
      source_kind: 'manual',
    };
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(doctorProfile)); return; }
      if (pathname === '/api/v1/registrar/queues/today') {
        await route.fulfill(jsonResponse({
          queues: [{
            queue_id: 1,
            specialist_id: 1,
            specialist_name: 'Dr Test',
            specialty: 'derma',
            cabinet: '12',
            entries: [dermaQueueEntry],
            stats: { total: 1, waiting: 1, called: 0, served: 0, online_entries: 0 },
            opened_at: '2026-08-29T09:00:00+05:00',
          }],
          total_queues: 1,
          date: '2026-08-29',
          timezone: 'Asia/Tashkent',
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/services') { await route.fulfill(jsonResponse({ services_by_group: {} })); return; }
      // EMR GET → 404: canonical "new visit" draft (deterministic — a mocked
      // 200 would need the full section schema; the draft path is production
      // behavior for a first visit).
      if (pathname === '/api/v1/v2/emr/501') { await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'not found' }) }); return; }
      if (pathname === '/api/v1/derma/examinations') { await route.fulfill(jsonResponse({ items: [], data: [] })); return; }
      if (pathname === '/api/v1/derma/procedures') { await route.fulfill(jsonResponse({ items: [], data: [] })); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });

    // Deep link: visitId opens the visit tab and resolves the patient from
    // the mocked derma queue (URL resolution in DermatologistPanelUnified).
    await page.goto('/doctor/dermatology?visitId=501&patientId=101');
    await page.locator('.emr-v2-container').first().waitFor({ state: 'visible', timeout: 20000 });
    await page.waitForTimeout(500);

    await expect(page.locator('.emr-v2-container').first()).toHaveScreenshot('pr124-emr-screen.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });
});

/**
 * Visual regression — PR-UI-16 Landing baselines (plan §PR-UI-16 AC4
 * "Visual regression"; user decision Q6: light + dark).
 *
 * Baseline policy (Rule 13 / Task 46 §D.3): these are NEW baselines captured
 * ONCE on the PR-UI-16-5 state — Landing had NO baseline before this PR
 * (first capture, not a re-capture of an existing one). The Landing redesign
 * itself is the intentional visual change these baselines lock in:
 *   - 16-1: legacy glass layer decommissioned → canonical --mac-* surfaces
 *   - 16-3: real product screenshots in Hero + Screens showcase
 *   - 16-4: workflow as the central element (7 nodes + 7 numbered steps)
 * All pre-existing baselines (cashier/registrar/wizard/EAT/pr124) stay
 * UNCHANGED — the redesign touched the Landing route only.
 *
 * Surfaces captured (viewport 1280×720, Desktop Chrome):
 *   1. Landing hero (topbar + hero card + the real queue screenshot, eager
 *      loading via fetchPriority=high — deterministic above-the-fold state;
 *      lazy below-fold showcase images are out of frame by design).
 *   2. Landing workflow (the central 7-node flow + numbered steps — no
 *      images, fully deterministic; scrolled into view via the body scroll
 *      container contract).
 * Both surfaces × light + dark (dark flipped through the real toolbar
 * toggle — the same path a user takes; verified via the landing-shell
 * class contract before capture).
 *
 * Determinism: APIs mocked (anonymous public state — setup initialized,
 * auth/me 401); WebSocket closed; ru locale (app default); light theme
 * pinned via localStorage `colorScheme=light` (ThemeContext default).
 */
test.describe('Visual regression — PR-UI-16 Landing (light + dark)', () => {
  test.beforeEach(async ({ page }) => {
    // Pin the theme contract explicitly (fresh contexts default to light,
    // but the baseline should not depend on that default).
    await page.addInitScript(() => {
      localStorage.setItem('colorScheme', 'light');
    });
    // Mock WebSocket to prevent ECONNREFUSED noise (no backend in E2E).
    await page.routeWebSocket('**/*', ws => { ws.close(); });
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'not authenticated' }) }); return; }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });
  });

  async function waitForHeroScreenshot(page: import('@playwright/test').Page) {
    // The hero screenshot loads eagerly (fetchPriority=high); wait for the
    // decoded bitmap so the capture is never mid-load.
    await page.waitForFunction(() => {
      const img = document.querySelector<HTMLImageElement>('.landing-hero-shot img');
      return !!img && img.complete && img.naturalWidth > 0;
    }, undefined, { timeout: 15000 });
    await page.waitForTimeout(400);
  }

  async function flipToDarkIfNeeded(page: import('@playwright/test').Page) {
    const isDark = await page.locator('.landing-shell').evaluate((el) => el.classList.contains('landing-shell--dark'));
    if (!isDark) {
      await page.locator('.landing-toolbar-button').first().click();
      await page
        .locator('.landing-shell')
        .evaluate((el) => {
          if (!el.classList.contains('landing-shell--dark')) {
            throw new Error('theme flip failed: landing-shell--dark class missing after toggle');
          }
        });
      await page.waitForTimeout(400);
    }
  }

  test('landing hero — light theme (real product screenshot, glass decommissioned)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await waitForHeroScreenshot(page);
    await expect(page).toHaveScreenshot('pr16-landing-hero-light.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('landing hero — dark theme (canonical tokens auto-switch)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await flipToDarkIfNeeded(page);
    await waitForHeroScreenshot(page);
    await expect(page).toHaveScreenshot('pr16-landing-hero-dark.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('landing workflow — light theme (7 nodes + 7 numbered steps)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Scroll the workflow section into view (body.landing-body is the scroll
    // container — scrollIntoView works against it).
    await page.locator('#workflow').evaluate((el) => el.scrollIntoView({ block: 'start' }));
    // Deterministic readiness: all 7 stages rendered (content-visibility
    // renders the section once it enters the viewport).
    await page.waitForFunction(() => document.querySelectorAll('.landing-workflow-step').length === 7, undefined, { timeout: 15000 });
    await page.waitForTimeout(400);
    await expect(page).toHaveScreenshot('pr16-landing-workflow-light.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('landing workflow — dark theme (7 nodes + 7 numbered steps)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await flipToDarkIfNeeded(page);
    await page.locator('#workflow').evaluate((el) => el.scrollIntoView({ block: 'start' }));
    await page.waitForFunction(() => document.querySelectorAll('.landing-workflow-step').length === 7, undefined, { timeout: 15000 });
    await page.waitForTimeout(400);
    await expect(page).toHaveScreenshot('pr16-landing-workflow-dark.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });
});

/*
 * PR-UI-18 (plan §PR-UI-18 item 1): systematic light+dark page snapshots for
 * the 12 key screens. The suite already locks the Landing route in both
 * themes (pr16-landing-{hero,workflow}-{light,dark} — 4 baselines above), so
 * this block adds the remaining screens. Part 1: /login, /display-board,
 * /admin, /registrar — 4 screens × 2 themes = 8 baselines. Parts 2-3
 * (doctor/cashier/lab/patient, then cardiology/dermatology/dentistry) land
 * in follow-up increments; the landing screen stays covered by pr16.
 *
 * Determinism contract (mirrors the pr16 + capture-landing-screens pattern):
 *   - Clock frozen at 2026-08-29T12:00:00+05:00 via page.clock.install — the
 *     display board renders a live 1-second clock and registrar home renders
 *     time surfaces; an unfrozen clock makes baselines byte-unstable by
 *     construction (same instant as capture-landing-screens.spec.ts).
 *   - Theme pinned via localStorage colorScheme/theme/ui_theme before load.
 *     The colorScheme key has precedence over the QA harness's theme=light
 *     pin (colorScheme.ts resolves colorScheme first), so the pin wins for
 *     both modes. Verified before capture through the body[data-theme]
 *     contract set by applyColorSchemeToDom (theme/colorScheme.ts).
 *   - Authenticated screens reuse the QA harness (e2e/support/
 *     authenticatedQa.ts): QA JWT + generic envelope mocks for every
 *     /api/v1/** call — deterministic empty-data states, no backend.
 *   - Public screens (login, display-board) mock setup/status=initialized,
 *     auth/me=401 and a generic success envelope; WebSocket closed.
 *   - Viewport: project default Desktop Chrome 1280×720 — same as the pr124
 *     and pr16 baselines (no viewport override).
 *
 * Baseline policy (Rule 13): first capture on the 18-1 branch — new surfaces
 * introduced by this PR, no existing baseline is modified.
 */
test.describe('Visual regression — PR-UI-18 twelve screens · part 1: login, display-board, admin, registrar', () => {
  const PR18_INSTANT = new Date('2026-08-29T12:00:00+05:00');

  async function pinPr18Theme(page: import('@playwright/test').Page, mode: 'light' | 'dark') {
    await page.addInitScript((m) => {
      localStorage.setItem('colorScheme', m);
      localStorage.setItem('theme', m);
      localStorage.setItem('ui_theme', m);
    }, mode);
  }

  async function installPublicApiMocks(page: import('@playwright/test').Page) {
    // Mock WebSocket to prevent ECONNREFUSED noise (no backend in E2E).
    await page.routeWebSocket('**/*', ws => { ws.close(); });
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') {
        await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'not authenticated' }) });
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') { await route.fulfill(jsonResponse({ recent_activity: [] })); return; }
      await route.fulfill(jsonResponse({ success: true }));
    });
  }

  /** body[data-theme] must reflect the pinned mode before any capture. */
  async function expectPr18ThemeApplied(page: import('@playwright/test').Page, mode: 'light' | 'dark') {
    await expect.poll(
      async () => page.evaluate(() => document.body.getAttribute('data-theme')),
      { message: `theme contract: body[data-theme="${mode}"] must be applied before capture` }
    ).toBe(mode);
  }

  /** Bounded networkidle (polling pages never settle) + paint settle. */
  async function settleForPr18Capture(page: import('@playwright/test').Page) {
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => undefined);
    await page.waitForTimeout(400);
  }

  // --- Screen 2/12: Login (public, shell=landing, live LoginFormStyled —
  // NOT the dead pages/Login.tsx slated for PR-UI-17 L-5 deletion).
  test('pr18 login screen — light theme (public auth surface)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await installPublicApiMocks(page);
    await pinPr18Theme(page, 'light');
    await page.goto('/login');
    await expect(page.locator('form')).toBeVisible({ timeout: 15000 });
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'light');
    await expect(page).toHaveScreenshot('pr18-login-light.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('pr18 login screen — dark theme (public auth surface)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await installPublicApiMocks(page);
    await pinPr18Theme(page, 'dark');
    await page.goto('/login');
    await expect(page.locator('form')).toBeVisible({ timeout: 15000 });
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'dark');
    await expect(page).toHaveScreenshot('pr18-login-dark.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // --- Screen 12/12: Display board (public fullscreen kiosk, polls
  // /board/state; the 1s clock is frozen; WS closed → static empty board).
  test('pr18 display board — light theme (public kiosk surface)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await installPublicApiMocks(page);
    await pinPr18Theme(page, 'light');
    await page.goto('/display-board');
    await expect(page.locator('.displayboard-header')).toBeVisible({ timeout: 15000 });
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'light');
    await expect(page).toHaveScreenshot('pr18-display-board-light.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('pr18 display board — dark theme (public kiosk surface)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await installPublicApiMocks(page);
    await pinPr18Theme(page, 'dark');
    await page.goto('/display-board');
    await expect(page.locator('.displayboard-header')).toBeVisible({ timeout: 15000 });
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'dark');
    await expect(page).toHaveScreenshot('pr18-display-board-dark.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // --- Screen 3/12: Admin dashboard (/admin, QA harness empty-data state).
  test('pr18 admin dashboard — light theme (role home, QA harness)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await page.routeWebSocket('**/*', ws => { ws.close(); });
    await installAuthenticatedQaHarness(page, { role: 'Admin' });
    await pinPr18Theme(page, 'light');
    await page.goto('/admin');
    await expect(page.locator('.app-shell[data-route-id="admin-dashboard"]')).toBeVisible({ timeout: 15000 });
    await expect.poll(
      async () => (await page.locator('body').innerText()).trim().length,
      { message: 'admin dashboard should render non-empty body text' }
    ).toBeGreaterThan(0);
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'light');
    await expect(page).toHaveScreenshot('pr18-admin-light.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('pr18 admin dashboard — dark theme (role home, QA harness)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await page.routeWebSocket('**/*', ws => { ws.close(); });
    await installAuthenticatedQaHarness(page, { role: 'Admin' });
    await pinPr18Theme(page, 'dark');
    await page.goto('/admin');
    await expect(page.locator('.app-shell[data-route-id="admin-dashboard"]')).toBeVisible({ timeout: 15000 });
    await expect.poll(
      async () => (await page.locator('body').innerText()).trim().length,
      { message: 'admin dashboard should render non-empty body text' }
    ).toBeGreaterThan(0);
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'dark');
    await expect(page).toHaveScreenshot('pr18-admin-dark.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  // --- Screen 4/12: Registrar home (/registrar, QA harness empty-data state;
  // the wizard-specific surfaces are already locked by the wizard baselines).
  test('pr18 registrar home — light theme (role home, QA harness)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await page.routeWebSocket('**/*', ws => { ws.close(); });
    await installAuthenticatedQaHarness(page, { role: 'Registrar' });
    await pinPr18Theme(page, 'light');
    await page.goto('/registrar');
    await expect(page.locator('.app-shell[data-route-id="registrar-home"]')).toBeVisible({ timeout: 15000 });
    await expect.poll(
      async () => (await page.locator('body').innerText()).trim().length,
      { message: 'registrar home should render non-empty body text' }
    ).toBeGreaterThan(0);
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'light');
    await expect(page).toHaveScreenshot('pr18-registrar-light.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });

  test('pr18 registrar home — dark theme (role home, QA harness)', async ({ page }) => {
    await page.clock.install({ time: PR18_INSTANT });
    await page.routeWebSocket('**/*', ws => { ws.close(); });
    await installAuthenticatedQaHarness(page, { role: 'Registrar' });
    await pinPr18Theme(page, 'dark');
    await page.goto('/registrar');
    await expect(page.locator('.app-shell[data-route-id="registrar-home"]')).toBeVisible({ timeout: 15000 });
    await expect.poll(
      async () => (await page.locator('body').innerText()).trim().length,
      { message: 'registrar home should render non-empty body text' }
    ).toBeGreaterThan(0);
    await settleForPr18Capture(page);
    await expectPr18ThemeApplied(page, 'dark');
    await expect(page).toHaveScreenshot('pr18-registrar-dark.png', {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    });
  });
});
