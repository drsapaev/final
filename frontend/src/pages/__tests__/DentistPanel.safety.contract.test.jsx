import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../..');
const PANEL_PATH = path.join(ROOT, 'pages/DentistPanelUnified.jsx');

const readSource = () =>
  fs.readFileSync(PANEL_PATH, 'utf8').replace(/\r\n/g, '\n');

const extractBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('DentistPanel safety guards contract (C-1, C-2, C-3)', () => {
  it('C-1: requires explicit confirm() before completing the visit', () => {
    const source = readSource();
    const completeBlock = extractBlock(
      source,
      'const handleCompleteVisit = async () => {',
      'try {',
    );

    // Must call confirm() — no auto-complete on a single click.
    expect(completeBlock).toContain('await confirm(confirmOptions)');
    expect(completeBlock).toContain('if (!ok) {');
    // Must use the shared useConfirm hook (not window.confirm).
    expect(source).toContain('const [confirm, confirmDialog] = useConfirm()');
    expect(source).not.toContain('window.confirm(');
  });

  it('C-2: uses useSessionTimeoutWarning hook from hooks/', () => {
    const source = readSource();

    // Hook must be imported from the shared module.
    expect(source).toContain('import { useSessionTimeoutWarning } from \'../hooks/useSessionTimeoutWarning\'');

    // Hook must be invoked with onWarning + onExpired handlers.
    expect(source).toContain('useSessionTimeoutWarning({');
    expect(source).toContain('onWarning:');
    expect(source).toContain('onExpired:');

    // onExpired must redirect to /login (force re-auth).
    expect(source).toContain('window.location.href = \'/login\'');

    // Warning dialog must be rendered when sessionWarning is truthy.
    // PR #1910 extracted inline dialog to <SessionWarningModal /> component.
    // PR #1922 regressed this test — re-fixed.
    expect(source).toMatch(/sessionWarning\s*&&\s*[{(]/);
    expect(source).toContain('<SessionWarningModal');
    expect(source).toContain('import SessionWarningModal');
  });

  it('C-3: defines CRITICAL_ICD10_CODES for dental K04/K10 diagnoses', () => {
    const source = readSource();
    const block = extractBlock(
      source,
      '// C-3 (UX audit, port of cardio P-020)',
      'const handleCompleteVisit',
    );

    // i18n-unification: CRITICAL_ICD10_CODES is now an array of code strings,
    // labels are in i18n locale files (dental.dental_panel_critical_K04/K10)
    expect(block).toContain("'K04'");
    expect(block).toContain("'K10'");
    expect(block).toContain('dental_panel_critical_');
  });

  it('C-3: getCriticalDiagnosisWarning matches ICD-10 codes by prefix', () => {
    const source = readSource();
    const block = extractBlock(
      source,
      'const getCriticalDiagnosisWarning = useCallback',
      'const handleCompleteVisit',
    );

    // Must use prefix matching so K04.0 / K04.9 / K049 all match K04.
    expect(block).toContain('.startsWith(prefix)');
    // i18n-unification: label is now loaded via tI18n()
    expect(block).toContain('label: tI18n(');
    expect(block).toContain('return null;');
  });

  it('C-3: completeVisit shows danger-intent confirm when ICD-10 matches critical code', () => {
    const source = readSource();
    const completeBlock = extractBlock(
      source,
      'const handleCompleteVisit = async () => {',
      'try {',
    );

    // Must compute criticalWarning from visitProtocol icd10 field.
    expect(completeBlock).toContain('getCriticalDiagnosisWarning(');
    expect(completeBlock).toContain('visitProtocol?.icd10');

    // Must branch into danger-intent confirm when criticalWarning is truthy.
    expect(completeBlock).toContain('if (criticalWarning) {');
    expect(completeBlock).toContain('intent: \'danger\'');
    // i18n-unification: confirm labels now use tI18n()
    expect(completeBlock).toContain("tI18n('dental.dental_panel_critical_confirm')");
    expect(completeBlock).toContain("tI18n('dental.dental_panel_critical_cancel')");

    // Must fall back to primary-intent confirm for non-critical diagnoses.
    expect(completeBlock).toContain('intent: \'primary\'');
  });

  it('C-3: does NOT use cardio-specific ICD-10 codes (I21/I22/I46/I50/I71/R57)', () => {
    const source = readSource();
    const block = extractBlock(
      source,
      '// C-3 (UX audit, port of cardio P-020)',
      'const handleCompleteVisit',
    );

    // Dental panel must not borrow cardio codes — it has its own K04/K10.
    expect(block).not.toContain('\'I21\'');
    expect(block).not.toContain('\'I22\'');
    expect(block).not.toContain('\'I46\'');
    expect(block).not.toContain('\'I50\'');
    expect(block).not.toContain('\'I71\'');
    expect(block).not.toContain('\'R57\'');
  });
});
