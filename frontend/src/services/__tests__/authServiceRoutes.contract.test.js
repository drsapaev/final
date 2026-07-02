import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { API_ENDPOINTS } from '../../api/endpoints.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authServicePath = path.resolve(__dirname, '../auth.js');

const readAuthServiceSource = () => fs.readFileSync(authServicePath, 'utf8');

describe('auth service route contract', () => {
  it('uses canonical authentication endpoints for login', () => {
    const source = readAuthServiceSource();

    expect(source).toContain("api.post('/authentication/login'");
  });

  it('does not call the stale auth login endpoint', () => {
    const source = readAuthServiceSource();

    expect(source).not.toContain("api.post('/auth/login'");
  });

  it('uses canonical authentication endpoints for logout and refresh', () => {
    const source = readAuthServiceSource();

    expect(source).toContain("api.post('/authentication/logout')");
    expect(source).toContain("api.post('/authentication/refresh'");
  });

  it('does not call stale auth lifecycle endpoints', () => {
    const source = readAuthServiceSource();

    expect(source).not.toContain("api.post('/auth/logout')");
    expect(source).not.toContain("api.post('/auth/refresh'");
  });

  it('exports the canonical logout endpoint constant', () => {
    expect(API_ENDPOINTS.AUTH.LOGIN).toBe('/authentication/login');
    expect(API_ENDPOINTS.AUTH.LOGOUT).toBe('/authentication/logout');
    expect(API_ENDPOINTS.AUTH.REFRESH).toBe('/authentication/refresh');
  });
});
