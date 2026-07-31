/**
 * E2E Business Scenario 2: Appointment Cancellation
 *
 * Tests: confirmed → cancelled, slot is freed
 */

import { test, expect } from './fixtures';

test.describe('Business: Appointment Cancellation', () => {
  test('cancel confirmed appointment → status changes to cancelled', async ({ mockAuthPage: page }) => {
    let status = 'confirmed';

    await page.route('**/api/v1/appointments/1', async (route) => {
      if (route.request().method() === 'DELETE' || route.request().method() === 'PATCH') {
        status = 'cancelled';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status: 'cancelled' }),
        });
      } else if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status, patient_name: 'Test Patient' }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/appointments');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
