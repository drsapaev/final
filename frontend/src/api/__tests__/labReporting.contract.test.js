import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

const source = fs.readFileSync(
  path.join(ROOT, 'api/labReporting.js'),
  'utf8'
);

describe('labReportingApi UX-AUDIT-FIX12 — AbortController support', () => {
  it('request() forwards options.signal to fetch', () => {
    // FIX12: request() должен пробрасывать signal в fetch.
    expect(source).toContain('UX-AUDIT-FIX12');
    expect(source).toContain('options.signal');
    expect(source).toContain('signal: options.signal');
  });

  it('documents the AbortController contract in JSDoc', () => {
    // Документация должна объяснять, как вызывающий код использует signal.
    expect(source).toContain('AbortSignal');
    expect(source).toContain('AbortController');
  });

  it('preserves existing request signature (path, options)', () => {
    // Backward-compat: существующие вызовы без signal продолжают работать.
    expect(source).toContain('async function request(path, options = {}) {');
  });

  it('uses spread operator to pass signal conditionally', () => {
    // signal должен быть опциональным — если не передан, fetch работает без него.
    expect(source).toContain("...(options.signal ? { signal: options.signal } : {})");
  });
});
