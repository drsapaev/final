// One-time browser verification for the shared-computer scenario.
// Drives a real Chromium against `vite preview` (built sw.js), fulfills
// /api/v1/* at the context level (intercepts SW-initiated fetches in
// modern Playwright), and asserts:
//   1. sensitive endpoints (payments, auth/me) are NEVER written to Cache Storage
//   2. cacheable endpoints (patients) are cached (offline contract intact)
//   3. offline: cacheable endpoint served from cache, sensitive ones fail
//   4. frontend Sentry smoke: an uncaught page error produces a 200 to the
//      Sentry ingest endpoint
import { chromium } from '@playwright/test';

const BASE = process.env.PREVIEW_URL || 'http://localhost:4173';
const results = [];
const ok = (name, cond) => {
  results.push(`${cond ? 'PASS' : 'FAIL'}  ${name}`);
  if (!cond) process.exitCode = 1;
};

const browser = await chromium.launch();
const context = await browser.newContext({ serviceWorkers: 'allow' });
await context.route('**/api/v1/**', (route) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ mock: true }) }),
);
const page = await context.newPage();
page.setDefaultTimeout(20000);
await page.goto(BASE + '/');
// Register explicitly (app-side registration may be lazy/conditional)
await page.evaluate(async () => {
  const reg = await navigator.serviceWorker.register('/sw.js');
  await navigator.serviceWorker.ready;
  await reg.update();
});
await page.waitForFunction(async () => {
  const reg = await navigator.serviceWorker.getRegistration();
  return !!reg?.active;
}, undefined, { timeout: 20000 });
results.push('PASS  service worker active');

const urls = ['/api/v1/payments/test', '/api/v1/auth/me', '/api/v1/patients'];
for (const u of urls) {
  const status = await page.evaluate(async (url) => (await fetch(url)).status, u);
  ok(`fetch ${u} via SW -> 200 (${status})`, status === 200);
}

const cachedUrls = await page.evaluate(async () => {
  const names = await caches.keys();
  const all = [];
  for (const n of names) {
    const c = await caches.open(n);
    all.push(...(await c.keys()).map((k) => new URL(k.url).pathname));
  }
  return all;
});
ok('payments NOT cached', !cachedUrls.includes('/api/v1/payments/test'));
ok('auth/me NOT cached', !cachedUrls.includes('/api/v1/auth/me'));
ok('patients cached (offline contract)', cachedUrls.includes('/api/v1/patients'));

await context.unroute('**/api/v1/**');
await context.setOffline(true);
const patientsOffline = await page.evaluate(async (u) => {
  try {
    return (await fetch(u)).status;
  } catch {
    return 'network-error';
  }
}, '/api/v1/patients');
ok(`offline patients served from cache (${patientsOffline})`, patientsOffline === 200);
const paymentsOffline = await page.evaluate(async (u) => {
  try {
    return (await fetch(u)).status;
  } catch {
    return 'network-error';
  }
}, '/api/v1/payments/test');
ok(`offline payments NOT served (${paymentsOffline})`, paymentsOffline === 503);
const authmeOffline = await page.evaluate(async (u) => {
  try {
    return (await fetch(u)).status;
  } catch {
    return 'network-error';
  }
}, '/api/v1/auth/me');
ok(`offline auth/me NOT served (${authmeOffline})`, authmeOffline === 503);
await context.setOffline(false);

// Frontend Sentry smoke: uncaught page error -> ingest returns 200
const isSentryIngest = (rawUrl) => {
  try {
    const { hostname } = new URL(rawUrl);
    return hostname === 'ingest.us.sentry.io' || hostname.endsWith('.ingest.us.sentry.io');
  } catch {
    return false;
  }
};
const sentryPromise = page
  .waitForResponse((r) => isSentryIngest(r.url()) && r.request().method() === 'POST', { timeout: 20000 })
  .then((r) => `sentry ingest ${r.status()}`)
  .catch(() => 'sentry ingest NOT seen');
await page.evaluate(() => {
  setTimeout(() => {
    throw new Error('smoke test sentry frontend (playwright, preview build)');
  }, 50);
});
const sentryResult = await sentryPromise;
ok(sentryResult, sentryResult === 'sentry ingest 200');

await browser.close();
console.log(results.join('\n'));
