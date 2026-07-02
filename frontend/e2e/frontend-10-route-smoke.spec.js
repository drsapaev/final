// @ts-check
import { test, expect } from '@playwright/test';

const PUBLIC_ROUTES = [
  { path: '/login', name: 'login' },
  { path: '/queue/join', name: 'queue join' },
  { path: '/payment/success', name: 'payment success callback' },
  { path: '/payment/cancel', name: 'payment cancel callback' },
];

const PROTECTED_ROUTES = [
  { path: '/admin', role: 'admin' },
  { path: '/registrar', role: 'registrar' },
  { path: '/doctor', role: 'doctor' },
  { path: '/lab', role: 'lab' },
];

async function clearAuthState(page) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
}

async function expectMountedApp(page) {
  await expect(page.locator('#root')).toBeVisible();
  await expect.poll(
    async () => (await page.locator('body').innerText()).trim().length,
    { message: 'route should render non-empty body text' }
  ).toBeGreaterThan(0);
}

test.describe('Frontend 10/10 route smoke', () => {
  for (const route of PUBLIC_ROUTES) {
    test(`public route renders: ${route.name}`, async ({ page }) => {
      await clearAuthState(page);
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });

      await expectMountedApp(page);

      if (route.path === '/login') {
        await expect(page.locator('input[type="text"], input[name="username"]').first()).toBeVisible();
        await expect(page.locator('input[type="password"]').first()).toBeVisible();
      }
    });
  }

  for (const route of PROTECTED_ROUTES) {
    test(`protected route redirects without credentials: ${route.role}`, async ({ page }) => {
      test.info().annotations.push({
        type: 'credential-source',
        description: 'none; smoke validates unauthenticated route guard only',
      });

      await clearAuthState(page);
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });

      await expect(page).toHaveURL(/\/login$/);
      await expect(page.locator('input[type="text"], input[name="username"]').first()).toBeVisible();
      await expect(page.locator('input[type="password"]').first()).toBeVisible();
    });
  }
});
