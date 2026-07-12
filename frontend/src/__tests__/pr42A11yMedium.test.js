/**
 * PR-42 — Frontend a11y medium: Medium-E + Medium-F + Medium-G.
 *
 * Tests for:
 * 1. Medium-E: at least one form component has <label htmlFor> association
 * 2. Medium-F: ResponsiveModal, ResponsiveForm, PhotoComparison do not use
 *    hardcoded backgroundColor: 'white' (breaks dark mode)
 * 3. Medium-G: ModernInput, ModernSelect do not use tabIndex={-1} on action icons
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const RESPONSIVE_MODAL = path.join(ROOT, 'src/components/ResponsiveModal.jsx');
const RESPONSIVE_FORM = path.join(ROOT, 'src/components/forms/ResponsiveForm.jsx');
const PHOTO_COMPARISON = path.join(ROOT, 'src/components/dermatology/PhotoComparison.jsx');
const MODERN_INPUT = path.join(ROOT, 'src/components/forms/ModernInput.jsx');
const MODERN_SELECT = path.join(ROOT, 'src/components/forms/ModernSelect.jsx');

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

  it('ResponsiveForm does not use hardcoded backgroundColor: white', () => {
    const src = fs.readFileSync(RESPONSIVE_FORM, 'utf-8');
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

// ---------- 3. Medium-G: tabIndex on action icons ----------

describe('Medium-G: tabIndex on action icons', () => {
  it('ModernInput does not use tabIndex={-1} on action icons', () => {
    const src = fs.readFileSync(MODERN_INPUT, 'utf-8');
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    expect(stripped).not.toMatch(/tabIndex\s*=\s*\{\s*-1\s*\}/);
  });

  it('ModernSelect does not use tabIndex={-1} on action icons', () => {
    const src = fs.readFileSync(MODERN_SELECT, 'utf-8');
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    expect(stripped).not.toMatch(/tabIndex\s*=\s*\{\s*-1\s*\}/);
  });
});

function collectSourceFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
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
