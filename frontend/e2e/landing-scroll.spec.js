import { expect, test } from '@playwright/test';

test.describe('Landing scroll behavior', () => {
  test('renders full landing content and allows scrolling to the footer', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const metricsBeforeScroll = await page.evaluate(() => ({
      scrollHeight: document.documentElement.scrollHeight,
      innerHeight: window.innerHeight,
      maxScroll: document.documentElement.scrollHeight - window.innerHeight,
    }));

    expect(metricsBeforeScroll.scrollHeight).toBeGreaterThan(metricsBeforeScroll.innerHeight);
    expect(metricsBeforeScroll.maxScroll).toBeGreaterThan(0);

    await page.evaluate(() => {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'auto' });
    });

    await page.waitForTimeout(250);

    const footer = page.locator('.landing-footer');
    await expect(footer).toBeVisible();
    await expect(footer).toBeInViewport();

    const scrollY = await page.evaluate(() => window.scrollY);
    expect(scrollY).toBeGreaterThan(0);
  });
});
