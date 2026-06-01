// @ts-check
import { test, expect } from '@playwright/test';
import {
  AUTHENTICATED_ROLE_QA_ROUTES,
  AUTHENTICATED_SPECIALTY_QA_ROUTES,
  installAuthenticatedQaHarness,
} from './support/authenticatedQa.js';

const AUTHENTICATED_ADMIN_ROUTE_FAMILY_QA_ROUTES = [
  {
    key: 'admin-overview-dashboard',
    path: '/admin',
    routeId: 'admin-dashboard',
  },
  {
    key: 'admin-management-users',
    path: '/admin/users',
    routeId: 'admin-users',
  },
  {
    key: 'admin-management-services',
    path: '/admin/services',
    routeId: 'admin-services',
  },
  {
    key: 'admin-management-appointments',
    path: '/admin/appointments',
    routeId: 'admin-appointments',
  },
  {
    key: 'admin-operations-system',
    path: '/admin/system',
    routeId: 'admin-system',
  },
  {
    key: 'admin-integrations-webhooks',
    path: '/admin/webhooks',
    routeId: 'admin-webhooks',
  },
  {
    key: 'admin-system-telegram',
    path: '/admin/integrations/telegram',
    routeId: 'admin-telegram-integration',
  },
  {
    key: 'admin-system-notifications',
    path: '/admin/notifications',
    routeId: 'admin-notifications',
  },
  {
    key: 'admin-system-finance',
    path: '/admin/finance',
    routeId: 'admin-finance',
  },
  {
    key: 'admin-contextual-clinic-settings',
    path: '/admin/clinic-settings?section=clinic-settings',
    routeId: 'admin-clinic-settings',
  },
];

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

async function expectVisibleRouteHeading(page, route) {
  const heading = page.locator('main').locator('h1, h2, h3, h4, h5, h6, [role="heading"]').filter({
    hasText: /\S/,
  }).first();

  await expect(heading, `${route.key} should expose a browser-visible heading`).toBeVisible({
    timeout: 15_000,
  });
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

async function runAdminRouteFamilyHeadingSmoke(page, testInfo, route) {
  const pageErrors = [];
  page.on('pageerror', (error) => {
    pageErrors.push(error.message);
  });

  await installAuthenticatedQaHarness(page, { role: 'Admin' });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(route.path, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => undefined);

  await expectRenderedRolePanel(page, route);
  await expectVisibleRouteHeading(page, route);
  await expectNoHorizontalOverflow(page, route);
  await expect(page.locator('body')).not.toContainText('AdminPanel');

  const screenshotPath = testInfo.outputPath(`admin-route-family-${route.key}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(`admin-route-family-${route.key}`, {
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

test.describe('Authenticated admin route family heading smoke', () => {
  for (const route of AUTHENTICATED_ADMIN_ROUTE_FAMILY_QA_ROUTES) {
    test(`${route.key} renders route-specific chrome and heading`, async ({ page }, testInfo) => {
      await runAdminRouteFamilyHeadingSmoke(page, testInfo, route);
    });
  }
});
