/**
 * PR-35 — Frontend Sprint 1 quick wins.
 *
 * Tests for:
 * 1. P0-7: BillingManager.jsx sanitizes HTML before document.write
 * 2. P0-14: DentistPanelUnified.jsx no longer calls loadPatients() twice in Promise.all
 * 3. High-8: prod nginx.conf has HSTS, COOP, COEP, CORP headers
 * 4. High-9: staging nginx.conf mirrors prod security headers
 * 5. Medium-10: connect-src no longer allows unencrypted ws: (any origin)
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const BILLING_MANAGER = path.join(ROOT, 'src/components/admin/BillingManager.tsx');
const DENTIST_PANEL = path.join(ROOT, 'src/pages/DentistPanelUnified.tsx');
const NGINX_PROD = path.join(ROOT, 'docker/nginx.conf');
const NGINX_STAGING = path.join(ROOT, 'docker/nginx.staging.conf');

// ---------- 1. P0-7: BillingManager sanitizes HTML ----------

describe('P0-7: BillingManager document.write sanitization', () => {
  const src = fs.readFileSync(BILLING_MANAGER, 'utf-8');

  it('imports sanitizePrintableHtml from printWindow', () => {
    expect(src).toMatch(/import\s+\{[^}]*sanitizePrintableHtml[^}]*\}\s+from\s+['"][^'"]*printWindow['"]/);
  });

  it('wraps response.data.html in sanitizePrintableHtml() before document.write', () => {
    // Strip comments so the explanatory comment mentioning the old pattern
    // doesn't trigger a false positive.
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have raw `document.write(response.data.html)`
    expect(stripped).not.toMatch(/document\.write\(\s*response\.data\.html\s*\)/);
    // Must have document.write(sanitizePrintableHtml(response.data.html))
    expect(stripped).toMatch(/document\.write\(\s*sanitizePrintableHtml\(\s*response\.data\.html\s*\)\s*\)/);
  });
});

// ---------- 2. P0-14: DentistPanelUnified no duplicate loadPatients ----------

describe('P0-14: DentistPanelUnified duplicate loadPatients removal', () => {
  const src = fs.readFileSync(DENTIST_PANEL, 'utf-8');

  it('does not have an executable Promise.all with two loadPatients() calls', () => {
    // Strip comments before checking — the comment explaining the fix is allowed
    // to mention the old buggy pattern.
    const stripped = src
      .replace(/\/\/.*$/gm, '')      // line comments
      .replace(/\/\*[\s\S]*?\*\//g, ''); // block comments
    // The old pattern: Promise.all([loadPatients(), loadPatients()])
    expect(stripped).not.toMatch(/Promise\.all\(\s*\[\s*loadPatients\(\),\s*loadPatients\(\)\s*\]/);
  });

  it('Promise.all blocks (excluding comments) contain at most one loadPatients() call', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    const promiseAllMatches = stripped.match(/Promise\.all\(\s*\[[^\]]+\]/g) || [];
    for (const block of promiseAllMatches) {
      const count = (block.match(/loadPatients\(\)/g) || []).length;
      expect(count).toBeLessThanOrEqual(1);
    }
  });
});

// ---------- 3. High-8: prod nginx security headers ----------

describe('High-8: prod nginx.conf security headers', () => {
  const src = fs.readFileSync(NGINX_PROD, 'utf-8');

  it('has HSTS header (Strict-Transport-Security)', () => {
    expect(src).toMatch(/Strict-Transport-Security.*max-age=31536000/);
  });

  it('has Cross-Origin-Opener-Policy (COOP)', () => {
    expect(src).toMatch(/Cross-Origin-Opener-Policy.*same-origin/);
  });

  it('has Cross-Origin-Embedder-Policy (COEP)', () => {
    expect(src).toMatch(/Cross-Origin-Embedder-Policy.*require-corp/);
  });

  it('has Cross-Origin-Resource-Policy (CORP)', () => {
    expect(src).toMatch(/Cross-Origin-Resource-Policy.*same-origin/);
  });
});

// ---------- 4. High-9: staging nginx mirrors prod ----------

describe('High-9: staging nginx.conf security headers', () => {
  const src = fs.readFileSync(NGINX_STAGING, 'utf-8');

  it('has X-Content-Type-Options', () => {
    expect(src).toMatch(/X-Content-Type-Options.*nosniff/);
  });

  it('has X-Frame-Options', () => {
    expect(src).toMatch(/X-Frame-Options.*DENY/);
  });

  it('has HSTS', () => {
    expect(src).toMatch(/Strict-Transport-Security/);
  });

  it('has Content-Security-Policy', () => {
    expect(src).toMatch(/Content-Security-Policy/);
  });
});

// ---------- 5. Medium-10: connect-src no unencrypted ws: ----------

describe('Medium-10: CSP connect-src tightened', () => {
  const prodSrc = fs.readFileSync(NGINX_PROD, 'utf-8');
  const stagingSrc = fs.readFileSync(NGINX_STAGING, 'utf-8');

  it('prod nginx does not allow ws: (unencrypted) as a standalone source in connect-src', () => {
    // The old CSP had: connect-src 'self' wss: ws:;
    // ws: (without s) allows unencrypted WebSocket to ANY origin.
    // We extract the connect-src directive and verify ws: is not present.
    const cspMatch = prodSrc.match(/Content-Security-Policy\s+"([^"]+)"/);
    expect(cspMatch).not.toBeNull();
    const csp = cspMatch[1];
    const connectSrcMatch = csp.match(/connect-src\s+([^;]+)/);
    expect(connectSrcMatch).not.toBeNull();
    const connectSrc = connectSrcMatch[1];
    // Must NOT contain standalone ws: (only wss: is OK)
    // Match ws: that is NOT preceded by 's' (i.e., not wss:)
    expect(connectSrc).not.toMatch(/(?<!s)ws:/);
  });

  it('staging nginx does not allow ws: (unencrypted) as a standalone source in connect-src', () => {
    const cspMatch = stagingSrc.match(/Content-Security-Policy\s+"([^"]+)"/);
    expect(cspMatch).not.toBeNull();
    const csp = cspMatch[1];
    const connectSrcMatch = csp.match(/connect-src\s+([^;]+)/);
    expect(connectSrcMatch).not.toBeNull();
    const connectSrc = connectSrcMatch[1];
    expect(connectSrc).not.toMatch(/(?<!s)ws:/);
  });
});
