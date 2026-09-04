import { expect, test } from '@playwright/test';

test.describe('Landing scroll behavior', () => {
  test('renders full landing content and allows scrolling to the footer', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Landing renders inside `body.landing-body { overflow-y: auto }`, which makes
    // <body> the scroll container — documentElement.scrollHeight stays at the
    // viewport height. Measure the real scroll container instead.
    const readMetrics = () =>
      page.evaluate(() => {
        const scrollHeight = Math.max(
          document.documentElement.scrollHeight,
          document.body.scrollHeight
        );
        return {
          scrollHeight,
          innerHeight: window.innerHeight,
          maxScroll: scrollHeight - window.innerHeight,
          scrollTop: Math.max(window.scrollY, document.body.scrollTop),
        };
      });

    const metricsBeforeScroll = await readMetrics();

    expect(metricsBeforeScroll.scrollHeight).toBeGreaterThan(metricsBeforeScroll.innerHeight);
    expect(metricsBeforeScroll.maxScroll).toBeGreaterThan(0);

    await page.evaluate(() => {
      const scrollHeight = Math.max(
        document.documentElement.scrollHeight,
        document.body.scrollHeight
      );
      // body.landing-body is the scroll container; also scroll the document for
      // environments where the document itself scrolls.
      document.body.scrollTop = scrollHeight;
      window.scrollTo({ top: scrollHeight, behavior: 'auto' });
    });

    await page.waitForTimeout(250);

    const footer = page.locator('.landing-footer');
    await expect(footer).toBeVisible();
    await expect(footer).toBeInViewport();

    const metricsAfterScroll = await readMetrics();
    expect(metricsAfterScroll.scrollTop).toBeGreaterThan(0);
  });
});
