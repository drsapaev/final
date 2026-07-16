/**
 * PR-38 — Frontend Sprint 3 quality: raw fetch → axios, dead code removal, silent catches.
 *
 * Tests for:
 * 1. High-21: usePatients.js no longer uses raw fetch() — migrated to api/patients.js
 * 2. High-22: Dead code removed (src/locales/ has 0 imports — verify it's gone or marked dead)
 * 3. Medium-23: Silent catches (empty catch blocks) reduced in flagged files
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const USE_PATIENTS = path.join(ROOT, 'src/hooks/usePatients.ts');

// ---------- 1. High-21: usePatients.js uses axios, not raw fetch ----------

describe('High-21: usePatients.js raw fetch → axios migration', () => {
  const src = fs.readFileSync(USE_PATIENTS, 'utf-8');

  it('does not use raw fetch() for patient CRUD operations', () => {
    // Strip comments
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have fetch(`...patients...`) calls
    expect(stripped).not.toMatch(/fetch\(\s*[`'"][^`'"]*\/patients\//);
  });

  it('imports api from api/client or api/patients', () => {
    // Either: import { api } from '../api/client'
    // Or:     import { ... } from '../api/patients'
    expect(src).toMatch(/from\s+['"][^'"]*api\/(?:client|patients)['"]/);
  });
});

// ---------- 2. High-22: Dead code removal ----------

describe('High-22: Dead code removal', () => {
  it('src/locales/ directory is removed or contains only a README/deprecation marker', () => {
    const localesDir = path.join(ROOT, 'src/locales');
    if (!fs.existsSync(localesDir)) {
      // Already removed — best outcome
      return;
    }
    // If it still exists, it should contain only a deprecation marker file
    // (README.md or DEPRECATED.md), not the 2801-LOC translation files.
    const entries = fs.readdirSync(localesDir, { withFileTypes: true });
    const jsFiles = entries.filter(
      (e) => e.isFile() && /\.(js|jsx|ts|tsx)$/.test(e.name)
    );
    // If there are .js files left, they must be small (deprecation stub only)
    for (const f of jsFiles) {
      const stat = fs.statSync(path.join(localesDir, f.name));
      expect(stat.size).toBeLessThan(500); // stub/deprecation marker only
    }
  });

  it('src/hooks/useUtils.js is not imported by production code (only by examples/)', () => {
    const useUtils = path.join(ROOT, 'src/hooks/useUtils.ts');
    if (!fs.existsSync(useUtils)) {
      return; // removed — best outcome
    }
    // Scan all source files (excluding examples/ and tests) for useUtils imports
    const srcDir = path.join(ROOT, 'src');
    const files = collectSourceFiles(srcDir);
    const productionImporters = [];
    for (const file of files) {
      if (file.includes('/examples/') || file.includes('/__tests__/')) continue;
      const src = fs.readFileSync(file, 'utf-8');
      if (/from\s+['"][^'"]*useUtils['"]/.test(src)) {
        productionImporters.push(path.relative(ROOT, file));
      }
    }
    expect(productionImporters).toEqual([]);
  });
});

// ---------- 3. Medium-23: Silent catches in Search.jsx ----------

describe('Medium-23: Silent catches in Search.jsx', () => {
  it('Search.jsx does not have empty catch blocks', () => {
    const searchFile = path.join(ROOT, 'src/pages/Search.jsx');
    const src = fs.readFileSync(searchFile, 'utf-8');
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Match: catch { } or catch (e) { } with NO body (only whitespace)
    // We allow catch (_e) { } (intentionally ignored, marked with underscore)
    // but not bare catch { } or catch (e) { } with no logging/handling.
    const silentCatchPattern = /catch\s*(?:\(\s*\w+\s*\))?\s*\{\s*\}/;
    expect(stripped).not.toMatch(silentCatchPattern);
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
