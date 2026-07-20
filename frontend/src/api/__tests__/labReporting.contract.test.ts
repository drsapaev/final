import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');

const source = fs.readFileSync(
  path.join(ROOT, 'api/labReporting.ts'),
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
    // Phase 1 TS migration: signature now has type annotations.
    expect(source).toMatch(/async function request\(path[^,]*,\s*options[^=]*=\s*\{\s*\}\)/);
  });

  it('uses spread operator to pass signal conditionally', () => {
    // signal должен быть опциональным — если не передан, fetch работает без него.
    expect(source).toContain("...(options.signal ? { signal: options.signal } : {})");
  });

  it('STRAT#4: listQueueToday accepts server-side pagination params', () => {
    // FIX: listQueueToday ранее принимал только targetDate. Теперь принимает
    // второй аргумент params = { limit, offset } для server-side pagination.
    expect(source).toContain('STRAT#4');
    // Phase 1 TS migration: params now have type annotations. Match the
    // signature either without (JS) or with (TS) type annotations on both
    // targetDate and params.
    expect(source).toMatch(/listQueueToday\(targetDate(?:\s*:[^=]+)?\s*=\s*null,\s*params(?:\s*:[^=]+)?\s*=\s*\{\s*\}\)/);
    // limit и offset пробрасываются в query string
    expect(source).toContain("params.limit !== undefined");
    expect(source).toContain("search.set('limit', String(params.limit))");
    expect(source).toContain("params.offset !== undefined");
    expect(source).toContain("search.set('offset', String(params.offset))");
  });
});
