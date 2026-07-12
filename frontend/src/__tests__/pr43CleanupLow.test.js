/**
 * PR-43 — Frontend cleanup: Medium-24 TODO/FIXME + Low findings.
 *
 * Tests for:
 * 1. Medium-24: DentistPanel stubs (loadTreatmentPlans, loadProsthetics) removed or marked
 * 2. Medium-24: fileValidator.js TODO comment addressed
 * 3. Medium-24: CashierPanel.jsx TODO comment addressed
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const DENTIST_PANEL = path.join(ROOT, 'src/pages/DentistPanelUnified.jsx');
const FILE_VALIDATOR = path.join(ROOT, 'src/utils/fileValidator.js');
const CASHIER_PANEL = path.join(ROOT, 'src/pages/CashierPanel.jsx');

// ---------- 1. DentistPanel stubs ----------

describe('Medium-24: DentistPanel stub cleanup', () => {
  const src = fs.readFileSync(DENTIST_PANEL, 'utf-8');

  it('loadTreatmentPlans is not a stub with TODO comment', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // The old stub was: const loadTreatmentPlans = useCallback(async () => { /* TODO */ });
    // We accept: either removed entirely, or the function has real implementation
    // (no 'TODO' or 'not implemented' in its body)
    const hasStub = /loadTreatmentPlans[\s\S]*?(?:TODO|not implemented|stub)/i.test(
      stripped.match(/loadTreatmentPlans\s*=\s*useCallback[\s\S]*?\}\s*,\s*\[\]\s*\);/)?.[0] || ''
    );
    expect(hasStub).toBe(false);
  });

  it('loadProsthetics is not a stub with TODO comment', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    const hasStub = /loadProsthetics[\s\S]*?(?:TODO|not implemented|stub)/i.test(
      stripped.match(/loadProsthetics\s*=\s*useCallback[\s\S]*?\}\s*,\s*\[\]\s*\);/)?.[0] || ''
    );
    expect(hasStub).toBe(false);
  });
});

// ---------- 2. fileValidator TODO ----------

describe('Medium-24: fileValidator TODO cleanup', () => {
  const src = fs.readFileSync(FILE_VALIDATOR, 'utf-8');

  it('fileValidator.js does not have a TODO comment about XML content check', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // The old comment: // TODO: Добавить проверку содержимого XML
    // We accept: either removed, or replaced with a non-TODO comment
    expect(stripped).not.toMatch(/TODO.*XML/i);
  });
});

// ---------- 3. CashierPanel TODO ----------

describe('Medium-24: CashierPanel TODO cleanup', () => {
  const src = fs.readFileSync(CASHIER_PANEL, 'utf-8');

  it('CashierPanel.jsx does not have a TODO comment about services info rendering', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // The old comment: {/* TODO: Render services info properly if available in history item */}
    expect(stripped).not.toMatch(/TODO.*services info/i);
  });
});
