// @ts-check
import { test, expect } from '@playwright/test';

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 834, height: 1112 },
  { name: 'mobile', width: 390, height: 844 },
];

const PUBLIC_EVIDENCE_ROUTES = [
  { path: '/login', name: 'login' },
  { path: '/queue/join', name: 'queue-join' },
  { path: '/payment/success', name: 'payment-success' },
  { path: '/payment/cancel', name: 'payment-cancel' },
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

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));

  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

async function expectIconButtonsNamed(page) {
  const unnamedIconButtons = await page.locator('button').evaluateAll((buttons) =>
    buttons
      .map((button, index) => {
        const text = (button.textContent || '').trim();
        const hasIcon = Boolean(button.querySelector('svg'));
        const hasName = Boolean(
          text ||
          button.getAttribute('aria-label') ||
          button.getAttribute('aria-labelledby') ||
          button.getAttribute('title')
        );

        return hasIcon && !hasName ? { index, html: button.outerHTML.slice(0, 160) } : null;
      })
      .filter(Boolean)
  );

  expect(unnamedIconButtons).toEqual([]);
}

async function expectKeyboardFocus(page) {
  const focusableCount = await page.locator(
    'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
  ).count();

  if (focusableCount === 0) {
    return;
  }

  await page.keyboard.press('Tab');
  const hasFocusedElement = await page.evaluate(() => {
    const active = document.activeElement;
    return Boolean(active && active !== document.body && active !== document.documentElement);
  });

  expect(hasFocusedElement).toBe(true);
}

test.describe('Frontend 10/10 public visual and a11y evidence', () => {
  for (const viewport of VIEWPORTS) {
    for (const route of PUBLIC_EVIDENCE_ROUTES) {
      test(`${route.name} ${viewport.name}`, async ({ page }, testInfo) => {
        await clearAuthState(page);
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.goto(route.path, { waitUntil: 'domcontentloaded' });

        await expectMountedApp(page);
        await expectNoHorizontalOverflow(page);
        await expectIconButtonsNamed(page);
        await expectKeyboardFocus(page);

        const screenshotPath = testInfo.outputPath(`${route.name}-${viewport.name}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true });
        await testInfo.attach(`${route.name}-${viewport.name}`, {
          path: screenshotPath,
          contentType: 'image/png',
        });
      });
    }
  }
});
