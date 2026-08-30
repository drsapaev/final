/**
 * PR-42 — Frontend a11y medium: Medium-F (residual).
 *
 * Tests for:
 *   Medium-F: ResponsiveModal, ResponsiveForm, PhotoComparison do not use
 *    hardcoded backgroundColor: 'white' (breaks dark mode)
 *
 * Note (PR-UI-17-2, 2026-08-30):
 *   Medium-E (label htmlFor association) and Medium-G (tabIndex on action icons)
 *   tested the dead Modern{Form,Input,Select,Textarea} components, which were
 *   removed in PR-UI-17-2 (dead-code cleanup; see docs/UI_REMEDIATION_PLAN.md §7
 *   PR-UI-17 item 2). Those two describe blocks removed together with the
 *   files; the surviving canonical form component ResponsiveForm does not
 *   currently use <label htmlFor> — adding that association is tracked
 *   separately outside PR-UI-17 scope.
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const RESPONSIVE_MODAL = path.join(ROOT, 'src/components/ResponsiveModal.tsx');
const RESPONSIVE_FORM = path.join(ROOT, 'src/components/forms/ResponsiveForm.tsx');
const PHOTO_COMPARISON = path.join(ROOT, 'src/components/dermatology/PhotoComparison.tsx');

// ---------- Medium-F: dark mode backgroundColor ----------

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
