import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { API_ENDPOINTS } from '../endpoints';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const apiDir = path.resolve(__dirname, '..');

const readSource = (fileName: string): string => fs.readFileSync(path.join(apiDir, fileName), 'utf8');

describe('auth login API contract', () => {
  it('uses the canonical authentication login route in the API helper', () => {
    const clientSource = readSource('client.ts');

    expect(clientSource).toContain('api.post(\'/authentication/login\'');
    expect(clientSource).not.toContain('api.post(\'/auth/login\'');
  });

  it('uses the canonical authentication login route in endpoint constants', () => {
    expect(API_ENDPOINTS.AUTH.LOGIN).toBe('/authentication/login');
  });
});
