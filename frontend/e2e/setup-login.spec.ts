// @ts-check
import { test, expect } from '@playwright/test';

const SETUP_CTA_NAME = '\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043a\u043b\u0438\u043d\u0438\u043a\u0443';
const LEGACY_REGISTER_NAME = '\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f';

async function openLoginWithSetupStatus(page, initialized) {
  const setupStatusRequests = [];

  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  await page.route('**/api/v1/setup/status', async (route) => {
    setupStatusRequests.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ initialized }),
    });
  });

  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('input[name="username"]')).toBeVisible();
  await expect.poll(() => setupStatusRequests.length).toBeGreaterThan(0);

  return setupStatusRequests;
}

test.describe('Login setup entrypoint', () => {
  test('shows setup CTA only before clinic initialization', async ({ page }) => {
    await openLoginWithSetupStatus(page, false);

    await expect(page.getByRole('button', { name: SETUP_CTA_NAME })).toBeVisible();
    await expect(page.getByRole('button', { name: LEGACY_REGISTER_NAME })).toHaveCount(0);
  });

  test('navigates setup CTA to canonical setup route', async ({ page }) => {
    await openLoginWithSetupStatus(page, false);

    await page.getByRole('button', { name: SETUP_CTA_NAME }).click();

    await expect(page).toHaveURL(/\/setup$/);
  });

  test('hides setup CTA after clinic initialization', async ({ page }) => {
    await openLoginWithSetupStatus(page, true);

    await expect(page.getByRole('button', { name: SETUP_CTA_NAME })).toHaveCount(0);
    await expect(page.getByRole('button', { name: LEGACY_REGISTER_NAME })).toHaveCount(0);
    await expect(page).toHaveURL(/\/login$/);
  });
});
