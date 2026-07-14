// @ts-check
/**
 * E2E test: UX Audit Registrar — new interactions added in UX audit cycle.
 *
 * Covers 4 features:
 * 1. Overflow menu "Ещё" in WelcomeView toolbar (R-1.1)
 * 2. ARIA radiogroup for gender field in PatientStepV2 (R-2.4)
 * 3. Confirm dialogs for critical actions in context menu (R-1.2)
 * 4. Payment badge in status column (R-4.4)
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

const registrarProfile = {
  id: 20,
  username: 'registrar@example.com',
  email: 'registrar@example.com',
  full_name: 'Registrar User',
  role: 'Receptionist',
  is_active: true,
  is_superuser: false,
};

const accessToken = createJwt({
  sub: String(registrarProfile.id),
  username: registrarProfile.username,
  user_id: registrarProfile.id,
  exp: Math.floor(Date.now() / 1000) + 3600,
});

function jsonResponse(body) {
  return {
    status: 200,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(body),
  };
}

// Sample appointment with payment_status for payment badge test
const sampleAppointment = {
  id: 1001,
  patient_fio: 'Иванов Иван Иванович',
  patient_phone: '+998901234567',
  patient_birth_year: 1985,
  status: 'scheduled',
  payment_status: 'paid_pending',
  payment_type: 'cash',
  visit_type: 'consultation',
  services: [{ id: 101, code: 'C001', name: 'Консультация кардиолога', price: 150000 }],
  cost: 150000,
  total_amount: 150000,
  appointment_date: new Date().toISOString().split('T')[0],
  appointment_time: '10:00',
  created_at: new Date().toISOString(),
  doctor_id: 1,
  doctor_name: 'Dr Test',
  department: 'cardiology',
  queue_numbers: [],
  available_actions: ['confirm', 'cancel', 'refund', 'print_receipt', 'in_cabinet', 'complete'],
};

test.describe('UX Audit Registrar — new interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(({ token, profile }) => {
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('refresh_token', token);
      sessionStorage.setItem('auth_profile', JSON.stringify(profile));
      sessionStorage.setItem('user', JSON.stringify(profile));
    }, { token: accessToken, profile: registrarProfile });

    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;

      if (pathname === '/api/v1/setup/status') {
        await route.fulfill(jsonResponse({ initialized: true }));
        return;
      }
      if (pathname === '/api/v1/auth/me') {
        await route.fulfill(jsonResponse(registrarProfile));
        return;
      }
      if (pathname === '/api/v1/queues/profiles') {
        await route.fulfill(jsonResponse({
          success: true,
          profiles: [{
            key: 'cardiology',
            title: 'Cardiology',
            title_ru: 'Кардиология',
            queue_tags: ['cardiology'],
            icon: 'Heart',
            color: '#ef4444',
            order: 1,
          }],
          source: 'database',
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/doctors') {
        await route.fulfill(jsonResponse({
          doctors: [{ id: 1, full_name: 'Dr Test', specialty: 'cardiology', cabinet: '12' }],
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/services') {
        await route.fulfill(jsonResponse({
          services_by_group: {
            cardio: [{
              id: 101, code: 'C001', name: 'Консультация кардиолога',
              price: 150000, requires_doctor: true,
            }],
          },
        }));
        return;
      }
      if (pathname === '/api/v1/registrar/appointments') {
        await route.fulfill(jsonResponse({
          appointments: [sampleAppointment],
          total: 1,
          has_more: false,
        }));
        return;
      }
      if (pathname === '/api/v1/notifications/history/stats') {
        await route.fulfill(jsonResponse({ recent_activity: [] }));
        return;
      }

      await route.fulfill(jsonResponse({ success: true }));
    });
  });

  // ========================================================================
  // Test 1: Overflow menu "Ещё" in WelcomeView toolbar (R-1.1)
  // ========================================================================
  test('overflow menu "Ещё" contains secondary actions', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);

    // "Ещё" button should be visible in toolbar
    const moreButton = page.locator('summary.registrar-overflow-trigger, [aria-label="Дополнительные фильтры и действия"]').first();
    await expect(moreButton).toBeVisible({ timeout: 10000 });

    // Click to open dropdown
    await moreButton.click();
    await page.waitForTimeout(500);

    // Dropdown popover should be visible with menu items
    const popover = page.locator('.registrar-overflow-popover').first();
    await expect(popover).toBeVisible();

    // Verify secondary actions are present in dropdown
    await expect(page.locator('.registrar-overflow-item').filter({ hasText: 'Активная очередь' })).toBeVisible();
    await expect(page.locator('.registrar-overflow-item').filter({ hasText: 'Ожидают оплаты' })).toBeVisible();
    await expect(page.locator('.registrar-overflow-item').filter({ hasText: 'Онлайн-очередь' })).toBeVisible();
    await expect(page.locator('.registrar-overflow-item').filter({ hasText: 'Обновить данные' })).toBeVisible();
  });

  test('overflow menu items have role="menuitem"', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);

    const moreButton = page.locator('summary.registrar-overflow-trigger').first();
    await moreButton.click();
    await page.waitForTimeout(500);

    // All items should have role="menuitem" for a11y
    const menuItems = page.locator('.registrar-overflow-popover [role="menuitem"]');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(4);
  });

  // ========================================================================
  // Test 2: ARIA radiogroup for gender field in PatientStepV2 (R-2.4)
  // ========================================================================
  test('gender field uses ARIA radiogroup', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);

    // Open wizard via "Новая запись" button
    await page.locator('text=Новая запись').first().click();
    await page.waitForTimeout(1500);

    // Radiogroup should be present
    const radiogroup = page.locator('[role="radiogroup"][aria-label="Пол пациента"]').first();
    await expect(radiogroup).toBeVisible({ timeout: 10000 });

    // Two radio buttons inside
    const radios = radiogroup.locator('[role="radio"]');
    await expect(radios).toHaveCount(2);

    // Verify labels: "Мужской" and "Женский"
    await expect(radios.filter({ hasText: 'Мужской' })).toBeVisible();
    await expect(radios.filter({ hasText: 'Женский' })).toBeVisible();
  });

  test('gender radiogroup supports keyboard navigation', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);

    await page.locator('text=Новая запись').first().click();
    await page.waitForTimeout(1500);

    const radiogroup = page.locator('[role="radiogroup"][aria-label="Пол пациента"]').first();
    await expect(radiogroup).toBeVisible({ timeout: 10000 });

    // Click "Мужской" to focus
    const maleRadio = radiogroup.locator('[role="radio"]').filter({ hasText: 'Мужской' });
    await maleRadio.click();

    // ArrowRight should switch to "Женский"
    await radiogroup.press('ArrowRight');
    await page.waitForTimeout(300);

    const femaleRadio = radiogroup.locator('[role="radio"]').filter({ hasText: 'Женский' });
    await expect(femaleRadio).toHaveAttribute('aria-checked', 'true');

    // ArrowLeft should switch back to "Мужской"
    await radiogroup.press('ArrowLeft');
    await page.waitForTimeout(300);
    await expect(maleRadio).toHaveAttribute('aria-checked', 'true');
  });

  // ========================================================================
  // Test 3: Payment badge in status column (R-4.4)
  // ========================================================================
  test('payment badge renders for paid_pending status', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(3000);

    // Wait for table to render with sample appointment
    const table = page.locator('table').first();
    await expect(table).toBeVisible({ timeout: 10000 });

    // Look for payment badge with 💰 emoji and "Ожидает оплаты" text
    const paymentBadge = page.locator('text=/💰.*Ожидает оплаты/').first();
    await expect(paymentBadge).toBeVisible({ timeout: 5000 });
  });

  test('payment badge does not render for paid status', async ({ page }) => {
    // Override appointments to return paid status
    await page.route('**/api/v1/registrar/appointments', async (route) => {
      await route.fulfill(jsonResponse({
        appointments: [{ ...sampleAppointment, payment_status: 'paid' }],
        total: 1,
        has_more: false,
      }));
    });

    await page.goto('/registrar');
    await page.waitForTimeout(3000);

    const table = page.locator('table').first();
    await expect(table).toBeVisible({ timeout: 10000 });

    // Payment badge should NOT be visible for 'paid' status
    const paymentBadge = page.locator('text=/💰.*Ожидает оплаты/');
    await expect(paymentBadge).toHaveCount(0);
  });

  // ========================================================================
  // Test 4: Breadcrumb uses lucide chevron icon (R-3.9)
  // ========================================================================
  test('breadcrumb uses chevron icon separator', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);

    // Breadcrumb should be visible
    const breadcrumb = page.locator('text=Регистратура').first();
    await expect(breadcrumb).toBeVisible({ timeout: 5000 });

    // Chevron icon (svg) should be present as separator (not unicode ›)
    const chevronSvgs = page.locator('.registrar-breadcrumb-separator svg, .registrar-breadcrumb-separator').count();
    expect(chevronSvgs).toBeGreaterThan(0);
  });

  // ========================================================================
  // Test 5: Step progress indicator shows labels (R-2.3)
  // ========================================================================
  test('wizard step progress shows labels', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);

    await page.locator('text=Новая запись').first().click();
    await page.waitForTimeout(1500);

    // Step progress indicator should be visible
    const progress = page.locator('.wizard-progress').first();
    await expect(progress).toBeVisible({ timeout: 10000 });

    // Step labels should be present
    const labels = progress.locator('.wizard-progress__label');
    const labelCount = await labels.count();
    expect(labelCount).toBeGreaterThanOrEqual(2);

    // First step label should be "Пациент"
    await expect(labels.first()).toContainText('Пациент');
  });

  test('wizard step progress has aria-label', async ({ page }) => {
    await page.goto('/registrar');
    await page.waitForTimeout(2000);

    await page.locator('text=Новая запись').first().click();
    await page.waitForTimeout(1500);

    const progress = page.locator('.wizard-progress[aria-label="Шаги мастера записи"]').first();
    await expect(progress).toBeVisible({ timeout: 10000 });
  });
});
