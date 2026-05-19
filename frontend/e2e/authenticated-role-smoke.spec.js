// @ts-check
import { test, expect } from '@playwright/test';
import {
  AUTHENTICATED_ROLE_QA_ROUTES,
  installAuthenticatedQaHarness,
} from './support/authenticatedQa.js';

async function expectRenderedRolePanel(page, route) {
  await expect(page).not.toHaveURL(/\/login$/);
  await expect(page).not.toHaveURL(/\/(?:forbidden|unauthorized)$/);
  await expect(page.locator(`.app-shell[data-route-id="${route.routeId}"]`)).toBeVisible({
    timeout: 15_000,
  });
  await expect.poll(
    async () => (await page.locator('body').innerText()).trim().length,
    { message: `${route.key} panel should render non-empty body text` }
  ).toBeGreaterThan(0);
}

test.describe('Authenticated role UI QA harness', () => {
  for (const route of AUTHENTICATED_ROLE_QA_ROUTES) {
    test(`${route.key} route renders with seeded ${route.role} session`, async ({ page }, testInfo) => {
      const pageErrors = [];
      page.on('pageerror', (error) => {
        pageErrors.push(error.message);
      });

      await installAuthenticatedQaHarness(page, { role: route.role });
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle').catch(() => undefined);

      await expectRenderedRolePanel(page, route);

      const screenshotPath = testInfo.outputPath(`authenticated-${route.key}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach(`authenticated-${route.key}`, {
        path: screenshotPath,
        contentType: 'image/png',
      });

      expect(pageErrors).toEqual([]);
    });
  }
});
