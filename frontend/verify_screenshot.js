const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto('http://localhost:6006/iframe.html?id=primitives-input--clearable&viewMode=story');

  await page.waitForSelector('button');

  // hover the clear button
  await page.hover('button');

  // wait a bit for tooltip to appear
  await page.waitForTimeout(1000);

  await page.screenshot({ path: 'input_clear_hover.png' });

  await browser.close();
})();
