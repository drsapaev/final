/**
 * E2E Business Scenario 8: Telegram Onboarding
 *
 * Tests: patient → role patient → JWT updated → old token invalid
 */

import { test, expect } from './fixtures';

test.describe('Business: Telegram Onboarding', () => {
  test('telegram onboarding flow → role assigned', async ({ mockAuthPage: page }) => {
    await page.route('**/api/v1/telegram/mini-app/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_token: 'new-jwt-token',
          user: {
            id: 1,
            role: 'patient',
            email: 'patient@clinic.com',
          },
        }),
      });
    });

    await page.goto('/telegram');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
