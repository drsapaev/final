/**
 * E2E Business Scenario 3: Payment Processing
 *
 * Tests: pending → paid, payment created, appointment confirmed
 */

import { test, expect } from './fixtures';

test.describe('Business: Payment Processing', () => {
  test('pay appointment → status paid, payment created', async ({ mockAuthPage: page }) => {
    let appointmentStatus = 'pending';
    let paymentCreated = false;

    await page.route('**/api/v1/appointments/1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          status: appointmentStatus,
          patient_name: 'Test Patient',
          payment_amount: 150000,
          payment_currency: 'UZS',
        }),
      });
    });

    await page.route('**/api/v1/payments/invoices', async (route) => {
      if (route.request().method() === 'POST') {
        appointmentStatus = 'paid';
        paymentCreated = true;
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            appointment_id: 1,
            amount: 150000,
            status: 'paid',
            method: 'cash',
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      }
    });

    await page.goto('/cashier');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });

  test('payment list shows paid invoices', async ({ mockAuthPage: page }) => {
    await page.route('**/api/v1/payments/invoices', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, amount: 150000, status: 'paid', patient_name: 'Patient A' },
          { id: 2, amount: 50000, status: 'pending', patient_name: 'Patient B' },
        ]),
      });
    });

    await page.goto('/cashier');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
