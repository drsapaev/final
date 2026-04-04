import { chromium } from '@playwright/test';

function fail(message) {
  console.error(`FAIL: ${message}`);
  process.exit(1);
}

function envFlag(name, fallback = false) {
  const value = process.env[name];
  if (value == null) {
    return fallback;
  }
  return ['1', 'true', 'yes', 'on'].includes(String(value).trim().toLowerCase());
}

function resolveExpectedWsOrigin(origin) {
  const parsed = new URL(origin);
  parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${parsed.protocol}//${parsed.host}`;
}

const publicUrl = process.env.PUBLIC_URL;
if (!publicUrl) {
  fail('Missing required environment variable: PUBLIC_URL');
}

const expectedCurrentOrigin = new URL(publicUrl).origin;
const expectedApiOrigin = process.env.EXPECTED_FRONTEND_API_ORIGIN || expectedCurrentOrigin;
const expectedWsOrigin = process.env.EXPECTED_FRONTEND_WS_ORIGIN || resolveExpectedWsOrigin(expectedApiOrigin);
const allowSplitOrigin = envFlag('FRONTEND_EXPECT_SPLIT_ORIGIN', false);
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined;

let browser;

try {
  browser = await chromium.launch({
    headless: true,
    executablePath,
  });
} catch (error) {
  const detail = error instanceof Error ? error.message : String(error);
  fail(
    'Unable to launch Playwright Chromium. Install browsers with "npx playwright install chromium" ' +
      `or set PLAYWRIGHT_EXECUTABLE_PATH. Detail: ${detail}`
  );
}

try {
  const page = await browser.newPage();
  await page.goto(publicUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(
    () => Boolean(window.__CLINIC_RUNTIME__?.apiOrigin && window.__CLINIC_RUNTIME__?.wsOrigin),
    { timeout: 15000 }
  );

  const resolved = await page.evaluate(() => ({
    currentOrigin: window.__CLINIC_RUNTIME__?.currentOrigin || window.location.origin,
    apiOrigin: window.__CLINIC_RUNTIME__?.apiOrigin || '',
    wsOrigin: window.__CLINIC_RUNTIME__?.wsOrigin || '',
    href: window.location.href,
  }));

  console.log(`CURRENT_ORIGIN=${resolved.currentOrigin}`);
  console.log(`RESOLVED_API_ORIGIN=${resolved.apiOrigin}`);
  console.log(`RESOLVED_WS_ORIGIN=${resolved.wsOrigin}`);

  if (resolved.currentOrigin !== expectedCurrentOrigin) {
    fail(
      `frontend current origin mismatch: expected ${expectedCurrentOrigin}, got ${resolved.currentOrigin} (${resolved.href})`
    );
  }

  if (!allowSplitOrigin && resolved.apiOrigin !== resolved.currentOrigin) {
    fail(
      `frontend API origin is not same-origin: current=${resolved.currentOrigin}, api=${resolved.apiOrigin}`
    );
  }

  if (resolved.apiOrigin !== expectedApiOrigin) {
    fail(`frontend API origin mismatch: expected ${expectedApiOrigin}, got ${resolved.apiOrigin}`);
  }

  if (!allowSplitOrigin && resolved.wsOrigin !== resolveExpectedWsOrigin(resolved.currentOrigin)) {
    fail(
      `frontend WS origin is not same-origin-derived: current=${resolved.currentOrigin}, ws=${resolved.wsOrigin}`
    );
  }

  if (resolved.wsOrigin !== expectedWsOrigin) {
    fail(`frontend WS origin mismatch: expected ${expectedWsOrigin}, got ${resolved.wsOrigin}`);
  }

  console.log('PASS: frontend_runtime_probe completed successfully');
} finally {
  if (browser) {
    await browser.close();
  }
}
