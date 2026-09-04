import { devices, expect, test } from '@playwright/test';

test.use({ ...devices['Pixel 5'] });

// Landing renders inside `body.landing-body { overflow-y: auto }`, which makes
// <body> the scroll container — documentElement.scrollHeight stays at the
// viewport height. All metrics below therefore combine both scroll roots.
function readLandingMetrics() {
  return {
    scrollHeight: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
    scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
    innerHeight: window.innerHeight,
    innerWidth: window.innerWidth,
    scrollTop: Math.max(window.scrollY, document.body.scrollTop),
  };
}

function scrollLandingToBottom() {
  const scrollHeight = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
  document.body.scrollTop = scrollHeight;
  window.scrollTo({ top: scrollHeight, behavior: 'auto' });
}

test.describe('Landing mobile scroll behavior', () => {
  test('allows vertical scrolling without horizontal overflow on mobile', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const metricsBeforeScroll = await page.evaluate(readLandingMetrics);

    expect(metricsBeforeScroll.scrollHeight).toBeGreaterThan(metricsBeforeScroll.innerHeight);
    expect(metricsBeforeScroll.scrollHeight - metricsBeforeScroll.innerHeight).toBeGreaterThan(0);
    expect(metricsBeforeScroll.scrollWidth).toBeLessThanOrEqual(metricsBeforeScroll.innerWidth + 1);

    await expect(page.getByRole('button', { name: /посмотреть интерфейс/i })).toBeVisible();

    const footer = page.locator('.landing-footer');
    const readFooterMetrics = () =>
      footer.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return {
          top: rect.top,
          bottom: rect.bottom,
          innerHeight: window.innerHeight,
          scrollTop: Math.max(window.scrollY, document.body.scrollTop),
        };
      });

    let footerMetrics = await readFooterMetrics();

    // Progressive rendering (content-visibility: auto) can grow the page while the
    // user moves down, so keep jumping to the current bottom until it settles.
    for (let attempt = 0; attempt < 8; attempt += 1) {
      footerMetrics = await readFooterMetrics();

      if (footerMetrics.top < footerMetrics.innerHeight && footerMetrics.bottom > 0) {
        break;
      }

      const beforeJump = await page.evaluate(readLandingMetrics);

      await page.evaluate(scrollLandingToBottom);
      await page.waitForTimeout(200);

      const afterJump = await page.evaluate(readLandingMetrics);

      if (afterJump.scrollTop === beforeJump.scrollTop && afterJump.scrollHeight === beforeJump.scrollHeight) {
        break;
      }
    }

    footerMetrics = await readFooterMetrics();
    await expect(footer).toBeVisible();

    expect(footerMetrics.top).toBeLessThan(footerMetrics.innerHeight);
    expect(footerMetrics.bottom).toBeGreaterThan(0);
    expect(footerMetrics.scrollTop).toBeGreaterThan(0);

    const metricsAfterScroll = await page.evaluate(readLandingMetrics);

    expect(metricsAfterScroll.scrollWidth).toBeLessThanOrEqual(metricsAfterScroll.innerWidth + 1);
  });
});
