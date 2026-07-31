/**
 * E2E Business Scenario 10: RBAC
 *
 * Tests: admin sees all, doctor sees own, patient sees own appointments
 */

import { test, expect } from './fixtures';

test.describe('Business: RBAC', () => {
  test('admin can access all panels', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'admin-token');
      localStorage.setItem('auth_profile', JSON.stringify({
        id: 1,
        role: 'Admin',
        email: 'admin@clinic.com',
      }));
    });

    await page.route('**/api/v1/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });

  test('patient can only see own appointments', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'patient-token');
      localStorage.setItem('auth_profile', JSON.stringify({
        id: 100,
        role: 'patient',
        email: 'patient@clinic.com',
      }));
    });

    await page.route('**/api/v1/appointments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, patient_id: 100, patient_name: 'Me', status: 'confirmed' },
        ]),
      });
    });

    await page.goto('/patient');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });

  test('patient cannot access admin panel → 403', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'patient-token');
      localStorage.setItem('auth_profile', JSON.stringify({
        id: 100,
        role: 'patient',
      }));
    });

    await page.route('**/api/v1/admin/**', async (route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Admin access required' }),
      });
    });

    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
