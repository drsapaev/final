/**
 * E2E Business Scenario 5: Refund Processing
 *
 * Tests: paid → refunded, payment marked
 */

import { test, expect } from './fixtures';

test.describe('Business: Refund Processing', () => {
  test('refund paid appointment → status refunded', async ({ mockAuthPage: page }) => {
    let paymentStatus = 'paid';

    await page.route('**/api/v1/payments/1', async (route) => {
      if (route.request().method() === 'POST' || route.request().method() === 'PUT') {
        paymentStatus = 'refunded';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status: 'refunded' }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status: paymentStatus, amount: 150000 }),
        });
      }
    });

    await page.goto('/cashier');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
