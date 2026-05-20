// @ts-check
import { test, expect } from '@playwright/test';
import {
  AUTHENTICATED_ROLE_QA_ROUTES,
  AUTHENTICATED_SPECIALTY_QA_ROUTES,
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

async function expectNoHorizontalOverflow(page, route) {
  await expect.poll(
    async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1),
    { message: `${route.key} route should not create horizontal document overflow` }
  ).toBe(true);
}

async function expectRouteSpecificEvidence(page, route) {
  if (route.summaryLabel) {
    await expect(page.getByRole('list', { name: route.summaryLabel })).toBeVisible();
  }
}

async function runAuthenticatedRouteSmoke(page, testInfo, route) {
  const pageErrors = [];
  page.on('pageerror', (error) => {
    pageErrors.push(error.message);
  });

  await installAuthenticatedQaHarness(page, { role: route.role });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(route.path, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => undefined);

  await expectRenderedRolePanel(page, route);
  await expectNoHorizontalOverflow(page, route);
  await expectRouteSpecificEvidence(page, route);

  const screenshotPath = testInfo.outputPath(`authenticated-${route.key}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(`authenticated-${route.key}`, {
    path: screenshotPath,
    contentType: 'image/png',
  });

  expect(pageErrors).toEqual([]);
}

test.describe('Authenticated role UI QA harness', () => {
  for (const route of AUTHENTICATED_ROLE_QA_ROUTES) {
    test(`${route.key} route renders with seeded ${route.role} session`, async ({ page }, testInfo) => {
      await runAuthenticatedRouteSmoke(page, testInfo, route);
    });
  }
});

test.describe('Authenticated specialty UI QA harness', () => {
  for (const route of AUTHENTICATED_SPECIALTY_QA_ROUTES) {
    test(`${route.key} route renders with seeded ${route.role} session`, async ({ page }, testInfo) => {
      await runAuthenticatedRouteSmoke(page, testInfo, route);
    });
  }
});
