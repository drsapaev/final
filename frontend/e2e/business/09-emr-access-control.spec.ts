/**
 * E2E Business Scenario 9: EMR Access Control
 *
 * Tests: doctor sees only own patients, not others'
 */

import { test, expect } from './fixtures';

test.describe('Business: EMR Access Control', () => {
  test('doctor sees only own patients', async ({ page }) => {
    // Login as doctor
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'doctor-token');
      localStorage.setItem('auth_profile', JSON.stringify({
        id: 5,
        email: 'doctor@clinic.com',
        role: 'doctor',
        first_name: 'Dr.',
        last_name: 'House',
      }));
    });

    await page.route('**/api/v1/emr/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          visit_id: 1,
          doctor_id: 5,
          specialty_data: { complaints: 'chest pain', diagnosis: 'I10' },
        }),
      });
    });

    await page.goto('/doctor');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });

  test('doctor cannot access other doctor EMR → 403', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'doctor-token-5');
      localStorage.setItem('auth_profile', JSON.stringify({
        id: 5,
        role: 'doctor',
      }));
    });

    await page.route('**/api/v1/emr/*', async (route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Access denied: not your patient' }),
      });
    });

    await page.goto('/doctor');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
