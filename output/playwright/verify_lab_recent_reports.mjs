import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'file:///C:/final/frontend/node_modules/playwright/index.mjs';

const outputDir = 'C:/final/output/playwright';
const storageStatePath = path.join(outputDir, 'lab-storage.json');
const screenshotPath = path.join(outputDir, 'lab-04-recent-reports.png');
const openedScreenshotPath = path.join(outputDir, 'lab-04-opened-existing-report.png');
const resultPath = path.join(outputDir, 'lab-04-recent-reports.json');
const frontendUrl = process.env.FRONTEND_URL || 'http://127.0.0.1:4173';
const injectedAuthToken = process.env.LAB_AUTH_TOKEN || '';
const networkEvents = [];
const consoleEvents = [];

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();

page.on('console', (message) => {
  consoleEvents.push({
    type: message.type(),
    text: message.text(),
  });
});

page.on('response', async (response) => {
  const url = response.url();
  if (!url.includes('/api/v1/lab/report-instances') && !url.includes('/api/v1/users/me/preferences')) {
    return;
  }
  let body = '';
  try {
    body = await response.text();
  } catch {
    body = '<unavailable>';
  }
  networkEvents.push({
    url,
    status: response.status(),
    body,
  });
});

try {
  const storageState = JSON.parse(await fs.readFile(storageStatePath, 'utf-8'));
  const storedOrigin = storageState.origins?.find((origin) => Array.isArray(origin.localStorage));
  const localStorageEntries = (storedOrigin?.localStorage || []).map((item) => ({ ...item }));
  if (injectedAuthToken) {
    const authTokenEntry = localStorageEntries.find((item) => item.name === 'auth_token');
    if (authTokenEntry) {
      authTokenEntry.value = injectedAuthToken;
    } else {
      localStorageEntries.push({ name: 'auth_token', value: injectedAuthToken });
    }
  }

  await page.goto(`${frontendUrl}/login`, { waitUntil: 'commit', timeout: 60_000 });
  await page.evaluate((entries) => {
    window.localStorage.clear();
    entries.forEach((entry) => {
      window.localStorage.setItem(entry.name, entry.value);
    });
  }, localStorageEntries);

  await page.goto(`${frontendUrl}/lab-panel?tab=reports`, { waitUntil: 'load', timeout: 60_000 });

  const recentHeading = page.getByText('Недавние лабораторные бланки');
  await recentHeading.waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(8000);

  const buttonTexts = (await page.locator('button').allTextContents()).map((text) => text.trim());
  const reportButton = page
    .locator('button')
    .filter({ hasText: /ОАК|Тестовый Пациент Регистратура/i })
    .last();
  const reportButtonCount = await reportButton.count();
  const bodyText = ((await page.locator('body').textContent()) || '').trim();
  await page.screenshot({ path: screenshotPath, fullPage: true });
  if (reportButtonCount === 0) {
    await fs.writeFile(
      resultPath,
      JSON.stringify(
        {
          page: 'lab-panel',
          mode: 'fresh-session-recent-reports',
          error: 'report-button-not-found',
          buttonTexts,
          bodyText,
          networkEvents,
          consoleEvents,
          screenshot: screenshotPath,
        },
        null,
        2
      )
    );
    throw new Error('Recent reports card rendered, but no existing report button was found');
  }

  const reportButtonText = (await reportButton.textContent())?.trim() || '';

  await reportButton.click();
  await page.waitForLoadState('load');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: openedScreenshotPath, fullPage: true });

  const headerLocator = page.locator('text=Бланк #').first();
  const statusLocator = page.locator('text=Напечатан').first();
  const printButton = page.getByRole('button', { name: 'Печать PDF' });
  const headerVisible = await headerLocator.isVisible().catch(() => false);
  const printVisible = await printButton.isVisible().catch(() => false);
  const statusVisible = await statusLocator.isVisible().catch(() => false);
  const statusBadge = statusVisible ? ((await statusLocator.textContent())?.trim() || '') : '';
  const headerText = headerVisible ? ((await headerLocator.textContent())?.trim() || '') : '';
  const openedBodyText = ((await page.locator('body').textContent()) || '').trim();
  if (!headerVisible && !printVisible) {
    await fs.writeFile(
      resultPath,
      JSON.stringify(
        {
          page: 'lab-panel',
          mode: 'fresh-session-recent-reports',
          error: 'report-open-did-not-hydrate',
          reportButtonText,
          headerText,
          statusBadge,
          openedBodyText,
          networkEvents,
          consoleEvents,
          screenshots: [screenshotPath, openedScreenshotPath],
        },
        null,
        2
      )
    );
    throw new Error('Existing report button opened, but the report editor did not hydrate');
  }

  await page.screenshot({ path: openedScreenshotPath, fullPage: true });

  await fs.writeFile(
    resultPath,
    JSON.stringify(
      {
        page: 'lab-panel',
        mode: 'fresh-session-recent-reports',
        reportButtonText,
        statusBadge,
        headerText,
        printVisible,
        networkEvents,
        consoleEvents,
        screenshots: [screenshotPath, openedScreenshotPath],
      },
      null,
      2
    )
  );
} finally {
  await context.close();
  await browser.close();
}
