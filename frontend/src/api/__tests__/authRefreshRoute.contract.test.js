import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { API_ENDPOINTS } from '../endpoints.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const apiDir = path.resolve(__dirname, '..');

const readSource = (fileName) => fs.readFileSync(path.join(apiDir, fileName), 'utf8');

describe('auth refresh API contract', () => {
  it('uses the canonical authentication refresh route for proactive refresh', () => {
    const clientSource = readSource('client.ts');

    expect(clientSource).toContain('buildApiUrl(\'/authentication/refresh\')');
    expect(clientSource).not.toContain('buildApiUrl(\'/auth/refresh\')');
  });

  it('uses the canonical authentication refresh route in endpoint constants', () => {
    expect(API_ENDPOINTS.AUTH.REFRESH).toBe('/authentication/refresh');
  });

  it('does not keep stale refresh route exceptions in interceptors', () => {
    const interceptorsSource = readSource('interceptors.js');
    // Note: interceptors.js is still .js — will be .ts after Phase 1 batch 4.
    // Test will need updating then; for now, file is .js.

    expect(interceptorsSource).toContain('requestUrl.includes(\'/authentication/refresh\')');
    expect(interceptorsSource).not.toContain('requestUrl.includes(\'/auth/refresh\')');
  });
});
