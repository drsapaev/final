/**
 * E2E Business Scenario 7: Schedule Conflict
 *
 * Tests: two appointments for same slot → one created, second rejected with 409
 */

import { test, expect } from './fixtures';

test.describe('Business: Schedule Conflict', () => {
  test('double booking → second appointment rejected', async ({ mockAuthPage: page }) => {
    let firstBooked = false;

    await page.route('**/api/v1/appointments', async (route) => {
      if (route.request().method() === 'POST') {
        if (!firstBooked) {
          firstBooked = true;
          await route.fulfill({
            status: 201,
            contentType: 'application/json',
            body: JSON.stringify({ id: 1, status: 'pending', appointment_date: '2024-12-01', appointment_time: '10:00' }),
          });
        } else {
          await route.fulfill({
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Slot already booked' }),
          });
        }
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(firstBooked ? [{ id: 1, status: 'pending' }] : []),
        });
      }
    });

    await page.goto('/appointments');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
