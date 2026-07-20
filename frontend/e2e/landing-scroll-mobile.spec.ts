import { devices, expect, test } from '@playwright/test';

test.use({ ...devices['Pixel 5'] });

test.describe('Landing mobile scroll behavior', () => {
  test('allows vertical scrolling without horizontal overflow on mobile', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const metricsBeforeScroll = await page.evaluate(() => ({
      scrollHeight: document.documentElement.scrollHeight,
      scrollWidth: document.documentElement.scrollWidth,
      innerHeight: window.innerHeight,
      innerWidth: window.innerWidth,
      maxScroll: document.documentElement.scrollHeight - window.innerHeight,
    }));

    expect(metricsBeforeScroll.scrollHeight).toBeGreaterThan(metricsBeforeScroll.innerHeight);
    expect(metricsBeforeScroll.maxScroll).toBeGreaterThan(0);
    expect(metricsBeforeScroll.scrollWidth).toBeLessThanOrEqual(metricsBeforeScroll.innerWidth + 1);

    await expect(page.getByRole('button', { name: /открыть демо/i })).toBeVisible();

    const footer = page.locator('.landing-footer');
    const readFooterMetrics = () =>
      footer.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return {
          top: rect.top,
          bottom: rect.bottom,
          innerHeight: window.innerHeight,
          scrollY: window.scrollY,
        };
      });

    let footerMetrics = null;

    // Progressive rendering can increase scrollHeight while the user moves down the page,
    // so we keep jumping to the current document bottom until the layout settles.
    for (let attempt = 0; attempt < 8; attempt += 1) {
      footerMetrics = await readFooterMetrics();

      if (footerMetrics.top < footerMetrics.innerHeight && footerMetrics.bottom > 0) {
        break;
      }

      const beforeJump = await page.evaluate(() => ({
        scrollY: window.scrollY,
        scrollHeight: document.documentElement.scrollHeight
      }));

      await page.evaluate(() => {
        window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'auto' });
      });
      await page.waitForTimeout(200);

      const afterJump = await page.evaluate(() => ({
        scrollY: window.scrollY,
        scrollHeight: document.documentElement.scrollHeight
      }));

      if (afterJump.scrollY === beforeJump.scrollY && afterJump.scrollHeight === beforeJump.scrollHeight) {
        break;
      }
    }

    footerMetrics = await readFooterMetrics();
    await expect(footer).toBeVisible();

    expect(footerMetrics.top).toBeLessThan(footerMetrics.innerHeight);
    expect(footerMetrics.bottom).toBeGreaterThan(0);
    expect(footerMetrics.scrollY).toBeGreaterThan(0);

    const metricsAfterScroll = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }));

    expect(metricsAfterScroll.scrollWidth).toBeLessThanOrEqual(metricsAfterScroll.innerWidth + 1);
  });
});
