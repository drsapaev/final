// Run with: node --test frontend/e2e-manual/sw-install-nostore-check.mjs
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { test } from 'node:test';
import { chromium } from '@playwright/test';

test('activates the worker without retaining no-store precache responses', { timeout: 25_000 }, async () => {
  const version = 'synthetic-install-check';
  const template = await readFile(new URL('../sw.template.js', import.meta.url), 'utf8');
  const script = template.replaceAll('__SW_BUILD_VERSION__', version);
  const requests = new Set();
  const server = createServer((request, response) => {
    requests.add(request.url);
    const isWorker = request.url === '/sw.js';
    const body = isWorker ? script : '<!doctype html><title>Synthetic worker fixture</title>';
    response.writeHead(200, {
      'Cache-Control': 'no-store',
      'Content-Type': isWorker ? 'application/javascript; charset=utf-8' : 'text/html; charset=utf-8',
      'Content-Length': Buffer.byteLength(body),
      Connection: 'close',
    });
    response.end(body);
  });
  await new Promise((resolve, reject) => server.listen(0, '127.0.0.1', resolve).once('error', reject));
  const origin = 'http://127.0.0.1:' + server.address().port;
  let browser;
  try {
    browser = await chromium.launch();
    const context = await browser.newContext({ serviceWorkers: 'allow' });
    const page = await context.newPage();
    await page.goto(origin + '/fixture', { timeout: 5_000 });
    await page.evaluate(async () => {
      const cache = await caches.open('clinic-offline-data');
      await cache.put('/login', new Response('stale synthetic page'));
      await cache.put('/fixture-kept', new Response('unrelated synthetic entry'));
      await navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' });
    });
    await page.waitForFunction(
      () => navigator.serviceWorker.controller?.state === 'activated',
      undefined,
      { timeout: 7_000 },
    );
    const snapshot = await page.evaluate(async (cacheName) => {
      const registration = await navigator.serviceWorker.getRegistration();
      const names = await caches.keys();
      return {
        state: registration?.active?.state,
        scope: registration?.scope,
        script: registration?.active?.scriptURL,
        hasStaticCache: names.includes(cacheName),
        installEntries: await (await caches.open(cacheName)).keys().then(keys => keys.length),
        staleLogin: Boolean(await caches.match('/login')),
        unrelatedEntry: Boolean(await caches.match('/fixture-kept')),
      };
    }, 'clinic-static-' + version);
    assert.ok(requests.has('/login'), 'the worker must request the stale target');
    assert.ok(requests.has('/mobile'), 'the worker must reach the later precache URLs');
    assert.deepEqual(snapshot, {
      state: 'activated',
      scope: origin + '/',
      script: origin + '/sw.js',
      hasStaticCache: true,
      installEntries: 0,
      staleLogin: false,
      unrelatedEntry: true,
    });
  } finally {
    try {
      await browser?.close();
    } finally {
      await new Promise(resolve => server.close(resolve));
    }
  }
});
