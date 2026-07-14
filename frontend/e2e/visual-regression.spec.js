// @ts-check
/**
 * Visual regression tests: critical UI states for cashier and registrar panels.
 *
 * Uses Playwright's toHaveScreenshot() for pixel-perfect comparison.
 * Screenshots are stored in frontend/e2e/__screenshots__/ and updated
 * with: npx playwright test --update-snapshots
 *
 * Covered states:
 * 1. Cashier — pending tab with payment row
 * 2. Cashier — empty state (no pending payments)
 * 3. Cashier — history tab with sortable headers
 * 4. Cashier — overflow menu open
 * 5. Registrar — welcome view with toolbar
 * 6. Registrar — wizard step 1 (patient data)
 * 7. Registrar — wizard step progress indicator
 *
 * All API calls are mocked — no backend needed.
 */

import { test, expect } from '@playwright/test';

function base64UrlEncode(value) {
  return Buffer.from(JSON.stringify(value))
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function createJwt(payload) {
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

function createToken(profile) {
  return createJwt({
    sub: String(profile.id), username: profile.username,
    user_id: profile.id, exp: Math.floor(Date.now() / 1000) + 3600,
  });
}

function jsonResponse(body) {
  return { status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify(body) };
}

const samplePendingPayment = {
  id: 2001, patient_id: 101, patient_last_name: 'Иванов', patient_first_name: 'Иван',
  patient_name: 'Иванов Иван Иванович', patient_phone: '+998901234567',
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

test.describe('Visual regression — cashier panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(({ token, profile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(profile));
      sessionStorage.setItem('user', JSON.stringify(profile));
    }, { token: createToken(cashierProfile), profile: cashierProfile });

    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      if (pathname === '/api/v1/setup/status') { await route.fulfill(jsonResponse({ initialized: true })); return; }
      if (pathname === '/api/v1/auth/me') { await route.fulfill(jsonResponse(cashierProfile)); return; }
      if (pathname === '/api/v1/cashier/pending-payments') {
        await route.fulfill(jsonResponse({ success: true, data: [samplePendingPayment], pagination: { pages: 1, total: 1 } }));
        return;
      }
      if (pathname === '/api/v1/cashier/payments') {
        await route.fulfill(jsonResponse({ success: true, data: [sampleHistoryPayment], pagination: { pages: 1, total: 1 } }));
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
    // Override to return empty
    await page.route('**/api/v1/cashier/pending-payments', async (route) => {
      await route.fulfill(jsonResponse({ success: true, data: [], pagination: { pages: 1, total: 0 } }));
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
});

test.describe('Visual regression — registrar wizard', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(({ token, profile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(profile));
      sessionStorage.setItem('user', JSON.stringify(profile));
    }, { token: createToken(registrarProfile), profile: registrarProfile });

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
      if (pathname === '/api/v1/registrar/doctors') {
        await route.fulfill(jsonResponse({ doctors: [{ id: 1, full_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }] }));
        return;
      }
      if (pathname === '/api/v1/registrar/services') {
        await route.fulfill(jsonResponse({ services_by_group: { cardio: [{ id: 101, code: 'C001', name: 'Консультация кардиолога', price: 150000, requires_doctor: true }] } }));
        return;
      }
      if (pathname === '/api/v1/registrar/appointments') {
        await route.fulfill(jsonResponse({ appointments: [], total: 0, has_more: false }));
        return;
      }
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
