import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const settingsPath = path.resolve(__dirname, '../Settings.tsx');

describe('Settings generic key/value route contract', () => {
  it('uses the published settings endpoint with axios response data and canonical PUT body', () => {
    const source = fs.readFileSync(settingsPath, 'utf8');

    expect(source).toContain('api.get(\'/settings\', { params: { category } })');
    expect(source).toContain('const data = res?.data ?? res;');
    expect(source).toContain('api.put(\'/settings\', { category, key, value })');
    expect(source).not.toContain('api.put(\'/settings\', { body: { category, key, value } })');
  });

  it('uses activation response data and the canonical activate body', () => {
    const source = fs.readFileSync(settingsPath, 'utf8');

    expect(source).toContain('api.get(\'/activation/status\')');
    expect(source).toContain('setStatus(st?.data ?? st ?? null);');
    expect(source).toContain('api.post(\'/activation/activate\', { key })');
    expect(source).toContain('const res = response?.data ?? response;');
    expect(source).not.toContain('api.post(\'/activation/activate\', { body: { key } })');
  });
});
