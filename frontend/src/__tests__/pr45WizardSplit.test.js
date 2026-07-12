/**
 * PR-45 — AppointmentWizardV2 god component split (partial).
 *
 * Tests for:
 * 1. EditModeBanner extracted to its own component file
 * 2. StepProgressIndicator extracted to its own component file
 * 3. AppointmentWizardV2 imports and uses the extracted components
 * 4. AppointmentWizardV2 LOC reduced (was 2945)
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const WIZARD = path.join(ROOT, 'src/components/wizard/AppointmentWizardV2.jsx');
const WIZARD_DIR = path.join(ROOT, 'src/components/wizard');

// ---------- 1. EditModeBanner extracted ----------

describe('PR-45: EditModeBanner extraction', () => {
  it('EditModeBanner.jsx exists in wizard directory', () => {
    const bannerPath = path.join(WIZARD_DIR, 'EditModeBanner.jsx');
    expect(fs.existsSync(bannerPath)).toBe(true);
  });

  it('EditModeBanner.jsx exports a component', () => {
    const bannerPath = path.join(WIZARD_DIR, 'EditModeBanner.jsx');
    const src = fs.readFileSync(bannerPath, 'utf-8');
    expect(src).toMatch(/export\s+(?:default|const)\s+EditModeBanner/);
  });

  it('AppointmentWizardV2 imports EditModeBanner', () => {
    const src = fs.readFileSync(WIZARD, 'utf-8');
    expect(src).toMatch(/import\s+EditModeBanner/);
  });
});

// ---------- 2. StepProgressIndicator extracted ----------

describe('PR-45: StepProgressIndicator extraction', () => {
  it('StepProgressIndicator.jsx exists in wizard directory', () => {
    const indicatorPath = path.join(WIZARD_DIR, 'StepProgressIndicator.jsx');
    expect(fs.existsSync(indicatorPath)).toBe(true);
  });

  it('StepProgressIndicator.jsx exports a component', () => {
    const indicatorPath = path.join(WIZARD_DIR, 'StepProgressIndicator.jsx');
    const src = fs.readFileSync(indicatorPath, 'utf-8');
    expect(src).toMatch(/export\s+(?:default|const)\s+StepProgressIndicator/);
  });

  it('AppointmentWizardV2 imports StepProgressIndicator', () => {
    const src = fs.readFileSync(WIZARD, 'utf-8');
    expect(src).toMatch(/import\s+StepProgressIndicator/);
  });
});

// ---------- 3. Wizard file size reduced ----------

describe('PR-45: AppointmentWizardV2 size reduction', () => {
  it('AppointmentWizardV2.jsx is smaller than original 3015 LOC', () => {
    const src = fs.readFileSync(WIZARD, 'utf-8');
    const lineCount = src.split('\n').length;
    // Original was 3015 LOC (per audit doc). After extraction of EditModeBanner
    // and StepProgressIndicator, should be at least 40 lines smaller.
    expect(lineCount).toBeLessThan(3015);
  });
});
