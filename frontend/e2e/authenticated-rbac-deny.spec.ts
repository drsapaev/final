// @ts-check
import { test, expect } from '@playwright/test';
import {
  AUTHENTICATED_RBAC_DENY_QA_ROUTES,
  installAuthenticatedQaHarness,
} from './support/authenticatedQa.js';

async function expectForbiddenForSeededRole(page, route) {
  await expect(page).not.toHaveURL(/\/login$/);
  await expect(page).toHaveURL(/\/forbidden$/);
  await expect(page.locator(`.app-shell[data-route-id="${route.deniedRouteId}"]`)).toHaveCount(0);
  await expect(page.locator('body')).toContainText('403');
}

test.describe('Authenticated RBAC denial UI QA harness', () => {
  for (const route of AUTHENTICATED_RBAC_DENY_QA_ROUTES) {
    test(`${route.key} redirects seeded ${route.role} session to forbidden`, async ({ page }, testInfo) => {
      const pageErrors = [];
      page.on('pageerror', (error) => {
        pageErrors.push(error.message);
      });

      await installAuthenticatedQaHarness(page, { role: route.role });
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle').catch(() => undefined);

      await expectForbiddenForSeededRole(page, route);

      const screenshotPath = testInfo.outputPath(`authenticated-rbac-deny-${route.key}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach(`authenticated-rbac-deny-${route.key}`, {
        path: screenshotPath,
        contentType: 'image/png',
      });

      expect(pageErrors).toEqual([]);
    });
  }
});
