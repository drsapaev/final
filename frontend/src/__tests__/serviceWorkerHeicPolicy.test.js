import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';

const serviceWorkerSource = fs
  .readFileSync(path.resolve(process.cwd(), 'public/sw.js'), 'utf8')
  .replace(/\r\n/g, '\n');

describe('service worker HEIC policy', () => {
  it('does not execute a remote HEIC converter from a CDN', () => {
    expect(serviceWorkerSource).not.toContain('https://cdn.skypack.dev/heic2any');
    expect(serviceWorkerSource).not.toMatch(/import\(['"`]https?:\/\/[^'"`]+heic2any/);
  });

  it('routes HEIC conversion messages to the app fallback path', () => {
    expect(serviceWorkerSource).toContain('type === \'CONVERT_HEIC\'');
    expect(serviceWorkerSource).toContain('HEIC conversion is handled by the app fallback');
    expect(serviceWorkerSource).toMatch(/success:\s*false/);
  });
});
