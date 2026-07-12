/**
 * PR-36 — Frontend Sprint 1 security: PHI localStorage + WS JWT subprotocol + file upload validation.
 *
 * Tests for:
 * 1. P0-1: OfflineIndicator does not store PHI in plaintext localStorage
 * 2. P0-3: WS auth uses Sec-WebSocket-Protocol subprotocol (not URL query ?token=)
 * 3. P0-4: At least one file upload component uses validateFile() from fileValidator.js
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const OFFLINE_INDICATOR = path.join(ROOT, 'src/components/mobile/OfflineIndicator.jsx');
const WS_AUTH = path.join(ROOT, 'src/utils/websocketAuth.js');
const WS_JS = path.join(ROOT, 'src/api/ws.js');

// ---------- 1. P0-1: No PHI in plaintext localStorage ----------

describe('P0-1: OfflineIndicator PHI localStorage', () => {
  const src = fs.readFileSync(OFFLINE_INDICATOR, 'utf-8');

  it('does not write cached_appointments to localStorage in plaintext', () => {
    // Strip comments before checking — the fix may mention the old pattern
    // in an explanatory comment.
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have localStorage.setItem('cached_appointments', ...) or
    // localStorage.setItem('cached_notifications', ...) writing raw data
    expect(stripped).not.toMatch(/localStorage\.setItem\(\s*['"]cached_appointments['"]/);
    expect(stripped).not.toMatch(/localStorage\.setItem\(\s*['"]cached_notifications['"]/);
  });

  it('if offline cache is kept, uses a non-PHI key or a safe storage helper', () => {
    // We accept either:
    // (a) the entire localStorage cache removed (no setItem for cached_*)
    // (b) a sanitization step that strips PHI fields before caching
    // (c) using sessionStorage instead of localStorage (slightly better)
    // The simplest correct fix is (a) — remove the cache entirely.
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Verify no raw JSON.stringify(data) is written to cached_* keys
    expect(stripped).not.toMatch(
      /localStorage\.setItem\(\s*['"]cached_(?:appointments|patients|notifications)['"]\s*,\s*JSON\.stringify\(\s*data\s*\)/,
    );
  });
});

// ---------- 2. P0-3: WS auth uses subprotocol, not URL query ----------

describe('P0-3: WebSocket auth via Sec-WebSocket-Protocol subprotocol', () => {
  const wsAuthSrc = fs.readFileSync(WS_AUTH, 'utf-8');
  const wsJsSrc = fs.readFileSync(WS_JS, 'utf-8');

  it('websocketAuth.js does not append ?token= to the URL', () => {
    // Strip comments before checking.
    const stripped = wsAuthSrc
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have urlParams.append('token', token) or ?token= in URL
    expect(stripped).not.toMatch(/urlParams\.append\(\s*['"]token['"]\s*,\s*token\s*\)/);
  });

  it('websocketAuth.js passes token via WebSocket subprotocol (second arg)', () => {
    // The fix should construct the WebSocket like:
    //   new WebSocket(url, [`bearer.${token}`])
    // or similar — passing an array as the second argument.
    const stripped = wsAuthSrc
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    expect(stripped).toMatch(/new\s+WebSocket\(\s*\w+\s*,\s*\[?[^\]]*token[^\]]*\]?\s*\)/);
  });

  it('api/ws.js does not append ?token= to the display board WS URL', () => {
    const stripped = wsJsSrc
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have ?token=${...} in the URL
    expect(stripped).not.toMatch(/['"`]\?token=\$\{[^}]+\}/);
  });
});

// ---------- 3. P0-4: At least one file upload uses validateFile() ----------

describe('P0-4: File upload validation via validateFile()', () => {
  it('at least one file-upload component imports and calls validateFile from fileValidator.js', () => {
    // Scan all source files for: import ... validateFile ... from '.../fileValidator'
    // AND a call to validateFile(...) somewhere in the same file.
    const srcDir = path.join(ROOT, 'src');
    const files = collectSourceFiles(srcDir);
    const filesUsingValidateFile = [];
    for (const file of files) {
      const src = fs.readFileSync(file, 'utf-8');
      if (/from\s+['"][^'"]*fileValidator['"]/.test(src) && /validateFile\s*\(/.test(src)) {
        filesUsingValidateFile.push(path.relative(ROOT, file));
      }
    }
    expect(filesUsingValidateFile.length).toBeGreaterThan(0);
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
