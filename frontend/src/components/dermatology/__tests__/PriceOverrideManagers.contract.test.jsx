import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(__dirname, '../../..', 'components');

const readComponent = (relativePath) =>
  fs.readFileSync(path.join(ROOT, relativePath), 'utf8').replace(/\r\n/g, '\n');

describe('specialist price override API client contract', () => {
  it('uses the authenticated api client for dermatology price override endpoints', () => {
    const source = readComponent('dermatology/PriceOverrideManager.jsx');

    expect(source).toContain('import { api } from \'../../api/client\'');
    expect(source).toContain('api.get(\'/derma/price-overrides\'');
    expect(source).toContain('api.post(\'/derma/price-override\'');
    expect(source).not.toContain('fetch(`${API_BASE}/derma/price-overrides');
    expect(source).not.toContain('fetch(`${API_BASE}/derma/price-override');
    expect(source).not.toContain('response.json()');
  });

  it('uses the authenticated api client for dental price override endpoints', () => {
    const source = readComponent('dental/DentalPriceManager.jsx');

    expect(source).toContain('import { api } from \'../../api/client\'');
    expect(source).toContain('api.get(\'/dental/price-overrides\'');
    expect(source).toContain('api.post(\'/dental/price-override\'');
    expect(source).not.toContain('fetch(`${API_BASE}/dental/price-overrides');
    expect(source).not.toContain('fetch(`${API_BASE}/dental/price-override');
    expect(source).not.toContain('response.json()');
  });
});
