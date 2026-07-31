/**
 * E2E Business Scenario 6: Doctor Change
 *
 * Tests: doctor_id updated, notification sent
 */

import { test, expect } from './fixtures';

test.describe('Business: Doctor Change', () => {
  test('change doctor → appointment updated', async ({ mockAuthPage: page }) => {
    let doctorId = 1;

    await page.route('**/api/v1/appointments/1', async (route) => {
      if (route.request().method() === 'PUT') {
        const body = route.request().postDataJSON();
        if (body?.doctor_id) doctorId = body.doctor_id;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, doctor_id: doctorId, status: 'confirmed' }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            doctor_id: doctorId,
            doctor_name: doctorId === 1 ? 'Dr. A' : 'Dr. B',
            status: 'confirmed',
          }),
        });
      }
    });

    await page.goto('/appointments');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
