import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/hooks/useLabToast.ts'),
  'utf8'
);

const workbenchSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabReportWorkbench.tsx'),
  'utf8'
);

// STRAT#24: numeric validation moved to ReportEditor component
const reportEditorSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/ReportEditor.tsx'),
  'utf8'
);

describe('useLabToast hook (STRAT#2)', () => {
  it('exports useLabToast function', () => {
    expect(source).toContain('export function useLabToast(');
  });

  it('imports toast from react-toastify for interactive toasts', () => {
    expect(source).toContain("from 'react-toastify'");
    expect(source).toContain('toast');
  });

  it('exposes simple delegates that call notify callback', () => {
    expect(source).toContain("success: (message) => notify('success', message)");
    expect(source).toContain("error: (message) => notify('error', message)");
    expect(source).toContain("info: (message) => notify('info', message)");
    expect(source).toContain("warning: (message) => notify('warning', message)");
  });

  it('exposes interactive methods that call toast directly', () => {
    expect(source).toContain('interactiveError: (message, options = {}) => toast.error(message, options)');
    expect(source).toContain('interactiveWarning: (message, options = {}) => toast.warning(message, options)');
    expect(source).toContain('interactiveInfo: (message, options = {}) => toast.info(message, options)');
  });

  it('has STRAT#2 marker and explains the 3-channel problem in JSDoc', () => {
    expect(source).toContain('STRAT#2');
    expect(source).toContain('3 канала');
    expect(source).toContain('Nielsen Heuristic #4');
  });
});

describe('LabReportWorkbench uses useLabToast (STRAT#2)', () => {
  it('imports useLabToast hook', () => {
    expect(workbenchSource).toContain("from './hooks/useLabToast'");
    expect(workbenchSource).toContain('useLabToast');
  });

  it('instantiates labToast with notify callback', () => {
    expect(workbenchSource).toContain('const labToast = useLabToast(notify)');
  });

  it('uses labToast.interactive* for numeric validation instead of direct toast', () => {
    // STRAT#2: 3 toast calls заменены на labToast.interactive*
    // STRAT#24: numeric validation moved to ReportEditor component
    expect(reportEditorSource).toContain('labToast.interactiveError(');
    expect(reportEditorSource).toContain('labToast.interactiveWarning(');
    expect(reportEditorSource).toContain('labToast.interactiveInfo(');
  });

  it('no longer calls toast.error/warning/info directly in numeric validation', () => {
    // STRAT#24: numeric validation block moved to ReportEditor component.
    // Check there for direct toast.* calls.
    const toastCallPattern = /toast\.(error|warning|info)\(/;
    // Находим все matches и проверяем, что их нет в numeric validation block
    // (между t('errors.invalid_numeric') и "return;")
    const numericBlockStart = reportEditorSource.indexOf("t('errors.invalid_numeric')");
    expect(numericBlockStart).toBeGreaterThan(-1);
    const numericBlockEnd = reportEditorSource.indexOf('return;', numericBlockStart);
    const numericBlock = reportEditorSource.slice(numericBlockStart, numericBlockEnd);
    expect(toastCallPattern.test(numericBlock)).toBe(false);
  });
});
