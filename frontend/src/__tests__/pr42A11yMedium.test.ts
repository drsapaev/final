/**
 * PR-42 — Frontend a11y medium: Medium-E + Medium-F.
 *
 * Tests for:
 * 1. Medium-E: at least one form component has <label htmlFor> association
 * 2. Medium-F: ResponsiveModal, PhotoComparison do not use hardcoded
 *    backgroundColor: 'white' (breaks dark mode)
 *
 * PR-UI-17-2: Medium-F ResponsiveForm + Medium-G ModernInput/ModernSelect
 * cases removed — dead components deleted (0 runtime importers).
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const RESPONSIVE_MODAL = path.join(ROOT, 'src/components/ResponsiveModal.tsx');
const PHOTO_COMPARISON = path.join(ROOT, 'src/components/dermatology/PhotoComparison.tsx');

// ---------- 1. Medium-E: label htmlFor association ----------

describe('Medium-E: label htmlFor association', () => {
  it('at least one form component uses <label htmlFor=...> association', () => {
    const srcDir = path.join(ROOT, 'src/components/forms');
    if (!fs.existsSync(srcDir)) {
      // Skip if no forms dir
      return;
    }
    const files = collectSourceFiles(srcDir);
    let found = false;
    for (const f of files) {
      const src = fs.readFileSync(f, 'utf-8');
      // Look for <label htmlFor=...> (JSX)
      if (/<label[^>]*htmlFor\s*=/.test(src)) {
        found = true;
        break;
      }
    }
    expect(found).toBe(true);
  });
});

// ---------- 2. Medium-F: dark mode backgroundColor ----------

describe('Medium-F: dark mode backgroundColor fix', () => {
  it('ResponsiveModal does not use hardcoded backgroundColor: white', () => {
    const src = fs.readFileSync(RESPONSIVE_MODAL, 'utf-8');
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    expect(stripped).not.toMatch(/backgroundColor:\s*['"]white['"]/);
    expect(stripped).not.toMatch(/backgroundColor:\s*['"]#fff['"]/);
    expect(stripped).not.toMatch(/backgroundColor:\s*['"]#ffffff['"]/i);
  });

  it('PhotoComparison does not use hardcoded backgroundColor: white', () => {
    const src = fs.readFileSync(PHOTO_COMPARISON, 'utf-8');
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    expect(stripped).not.toMatch(/backgroundColor:\s*['"]white['"]/);
    expect(stripped).not.toMatch(/backgroundColor:\s*['"]#fff['"]/);
    expect(stripped).not.toMatch(/backgroundColor:\s*['"]#ffffff['"]/i);
  });
});

function collectSourceFiles(dir: string) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = []
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectSourceFiles(fullPath));
      continue;
    }
    if (/\.(js|jsx|ts|tsx)$/.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
}
