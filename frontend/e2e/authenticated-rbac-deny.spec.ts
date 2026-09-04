// @ts-check
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
  AUTHENTICATED_RBAC_DENY_QA_ROUTES,
  attachRuntimeErrorCapture,
  installAuthenticatedQaHarness,
} from './support/authenticatedQa';
import type { DenyQaRoute } from './support/authenticatedQa';

async function expectForbiddenForSeededRole(page: Page, route: DenyQaRoute) {
  await expect(page).not.toHaveURL(/\/login$/);
  await expect(page).toHaveURL(/\/forbidden$/);
  await expect(page.locator(`.app-shell[data-route-id="${route.deniedRouteId}"]`)).toHaveCount(0);
  await expect(page.locator('body')).toContainText('403');
}

test.describe('Authenticated RBAC denial UI QA harness', () => {
  for (const route of AUTHENTICATED_RBAC_DENY_QA_ROUTES) {
    test(`${route.key} redirects seeded ${route.role} session to forbidden`, async ({ page }, testInfo) => {
      // PR-QA-04: adopt the role-smoke runtime crash-capture standard
      // (pageerror + CRASH-signature console.error). These deny tests are
      // destined for blocking Tier-1, so a masked React crash behind the
      // ErrorBoundary must fail them exactly like the role/specialty/
      // action suites. The positive /forbidden assertions below stay the
      // primary gates; these are the crash-parity gates.
      const { pageErrors, consoleErrors } = attachRuntimeErrorCapture(page);

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

      expect(pageErrors, `${route.key} unexpected pageerror`).toEqual([]);
      expect(consoleErrors, `${route.key} unexpected console.error (possible masked crash)`).toEqual([]);
    });
  }
});
