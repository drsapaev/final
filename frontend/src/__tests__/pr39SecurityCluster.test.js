/**
 * PR-39 — Frontend security cluster: P0-2, P0-5, P0-6, Medium-11, Medium-12.
 *
 * Tests for:
 * 1. Medium-11: CSRF bootstrap enabled by default (no env var needed)
 * 2. Medium-12: JWT token preview NOT logged to console in production
 * 3. P0-5: At least one production form uses useSafeInput or useSafeForm
 * 4. P0-6: CSP does NOT have 'unsafe-inline' for script-src (uses nonces or hashes)
 * 5. P0-2: tokenManager does NOT store tokens in localStorage (uses sessionStorage or memory)
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const CLIENT_JS = path.join(ROOT, 'src/api/client.js');
const TOKEN_MANAGER = path.join(ROOT, 'src/utils/tokenManager.ts');
const NGINX_PROD = path.join(ROOT, 'docker/nginx.conf');

// ---------- 1. Medium-11: CSRF bootstrap enabled by default ----------

describe('Medium-11: CSRF bootstrap default', () => {
  const src = fs.readFileSync(CLIENT_JS, 'utf-8');

  it('CSRF bootstrap is enabled by default (without VITE_CSRF_BOOTSTRAP=1)', () => {
    // The old code: const CSRF_BOOTSTRAP_ENABLED = import.meta.env.VITE_CSRF_BOOTSTRAP === '1';
    // This means CSRF is OFF unless explicitly enabled. Fix: default to ON.
    // We accept either:
    // (a) CSRF_BOOTSTRAP_ENABLED defaults to true (e.g., !== '0')
    // (b) The check is removed entirely and CSRF always bootstraps
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have the strict === '1' check that defaults to OFF
    expect(stripped).not.toMatch(/VITE_CSRF_BOOTSTRAP\s*===\s*['"]1['"]/);
  });
});

// ---------- 2. Medium-12: JWT preview not logged ----------

describe('Medium-12: JWT preview not logged', () => {
  const src = fs.readFileSync(CLIENT_JS, 'utf-8');

  it('does not log tokenPreview in the request interceptor', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have tokenPreview in logger output
    expect(stripped).not.toMatch(/tokenPreview/);
  });
});

// ---------- 3. P0-5: Sanitizers wired to at least one form ----------

describe('P0-5: Sanitizers wired to production forms', () => {
  it('at least one production form uses useSafeInput or useSafeForm', () => {
    const srcDir = path.join(ROOT, 'src');
    const files = collectSourceFiles(srcDir);
    const filesUsingSafeInput = [];
    for (const file of files) {
      if (file.includes('/examples/') || file.includes('/__tests__/')) continue;
      const src = fs.readFileSync(file, 'utf-8');
      if (/from\s+['"][^'"]*useSafeInput['"]/.test(src) || /from\s+['"][^'"]*useSafeForm['"]/.test(src)) {
        filesUsingSafeInput.push(path.relative(ROOT, file));
      }
    }
    expect(filesUsingSafeInput.length).toBeGreaterThan(0);
  });
});

// ---------- 4. P0-6: CSP script-src without unsafe-inline ----------

describe('P0-6: CSP script-src without unsafe-inline', () => {
  it('prod nginx CSP does not allow unsafe-inline for script-src', () => {
    const src = fs.readFileSync(NGINX_PROD, 'utf-8');
    const cspMatch = src.match(/Content-Security-Policy\s+"([^"]+)"/);
    expect(cspMatch).not.toBeNull();
    const csp = cspMatch[1];
    const scriptSrcMatch = csp.match(/script-src\s+([^;]+)/);
    expect(scriptSrcMatch).not.toBeNull();
    const scriptSrc = scriptSrcMatch[1];
    // Must NOT have 'unsafe-inline' for script-src
    // (style-src 'unsafe-inline' is acceptable for Tailwind, but script-src is XSS-critical)
    expect(scriptSrc).not.toMatch(/'unsafe-inline'/);
  });
});

// ---------- 5. P0-2: tokenManager does not use localStorage for tokens ----------

describe('P0-2: tokenManager storage', () => {
  const src = fs.readFileSync(TOKEN_MANAGER, 'utf-8');

  it('tokenManager does not store tokens in localStorage', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT use localStorage.setItem/getItem for auth_token or refresh_token
    // We accept sessionStorage or in-memory storage as alternatives.
    // The old code: localStorage.setItem('auth_token', ...)
    expect(stripped).not.toMatch(/localStorage\.setItem\(\s*['"]auth_token['"]/);
    expect(stripped).not.toMatch(/localStorage\.setItem\(\s*['"]refresh_token['"]/);
    expect(stripped).not.toMatch(/localStorage\.getItem\(\s*['"]auth_token['"]/);
    expect(stripped).not.toMatch(/localStorage\.getItem\(\s*['"]refresh_token['"]/);
  });
});

function collectSourceFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (fullPath.includes('__tests__')) continue;
      files.push(...collectSourceFiles(fullPath));
      continue;
    }
    if (/\.(js|jsx|ts|tsx)$/.test(entry.name) && !/\.(test|spec)\.(js|jsx|ts|tsx)$/.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
}
