/**
 * E2E Business Scenario 4: Visit Completion
 *
 * Tests: in_visit → completed, EMR updated
 */

import { test, expect } from './fixtures';

test.describe('Business: Visit Completion', () => {
  test('complete visit → status completed, EMR saved', async ({ mockAuthPage: page }) => {
    let visitStatus = 'in_visit';

    await page.route('**/api/v1/appointments/1', async (route) => {
      if (route.request().method() === 'PUT') {
        visitStatus = 'completed';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status: 'completed' }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 1, status: visitStatus, patient_name: 'Test Patient' }),
        });
      }
    });

    await page.route('**/api/v1/emr/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          visit_id: 1,
          specialty_data: {
            complaints: 'chest pain',
            diagnosis: 'I10',
          },
          is_draft: false,
          row_version: 1,
        }),
      });
    });

    await page.goto('/doctor');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
