import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const settingsPath = path.resolve(__dirname, '../Settings.jsx');

describe('Settings generic key/value route contract', () => {
  it('uses the published settings endpoint with axios response data and canonical PUT body', () => {
    const source = fs.readFileSync(settingsPath, 'utf8');

    expect(source).toContain("api.get('/settings', { params: { category } })");
    expect(source).toContain('const data = res?.data ?? res;');
    expect(source).toContain("api.put('/settings', { category, key, value })");
    expect(source).not.toContain("api.put('/settings', { body: { category, key, value } })");
  });
});
