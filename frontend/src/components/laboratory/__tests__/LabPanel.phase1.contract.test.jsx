import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const readSource = (relPath) =>
  fs.readFileSync(path.join(ROOT, relPath), 'utf8').replace(/\r\n/g, '\n');

describe('LabPanel Phase 1 safety contract (H-1, H-2, H-3)', () => {
  it('H-1: LabPanel imports and calls useSessionTimeoutWarning', () => {
    const source = readSource('pages/LabPanel.jsx');

    expect(source).toContain('from \'../hooks/useSessionTimeoutWarning\'');
    expect(source).toContain('useSessionTimeoutWarning({');
    expect(source).toContain('onWarning:');
    expect(source).toContain('onExpired:');
    expect(source).toContain('window.location.href = \'/login\'');
  });

  it('H-1: LabPanel renders a session timeout warning dialog', () => {
    const source = readSource('pages/LabPanel.jsx');

    expect(source).toContain('sessionWarning');
    expect(source).toContain('Сессия скоро истечёт');
    expect(source).toContain('Продлить сессию');
  });

  it('H-2: useLabHotkeys hook exists and is wired in LabPanel', () => {
    const hookSource = readSource('hooks/useLabHotkeys.js');
    const panelSource = readSource('pages/LabPanel.jsx');

    // Hook file exists with correct exports
    expect(hookSource).toContain('export const useLabHotkeys');
    expect(hookSource).toContain('switchTab');
    expect(hookSource).toContain('refreshData');
    expect(hookSource).toContain('clearSelection');

    // Hook is imported and called in LabPanel
    expect(panelSource).toContain('from \'../hooks/useLabHotkeys\'');
    expect(panelSource).toContain('useLabHotkeys({');
  });

  it('H-2: useLabHotkeys supports Ctrl+1/2/3 for tab switching', () => {
    const source = readSource('hooks/useLabHotkeys.js');

    expect(source).toContain('\'1\': \'queue\'');
    expect(source).toContain('\'2\': \'templates\'');
    expect(source).toContain('\'3\': \'reports\'');
    expect(source).toContain('F5');
    expect(source).toContain('Escape');
  });

  it('H-3: LabReportWorkbench has no English aria-labels for lab results', () => {
    const source = readSource('components/laboratory/LabReportWorkbench.jsx');

    // Must NOT contain the old English aria-label
    expect(source).not.toContain('Lab result for');

    // STRAT#24: field rendering moved to ReportEditor component.
    // Check there for the localized aria-label pattern.
    const reportEditorSource = readSource('components/laboratory/ReportEditor.jsx');
    expect(reportEditorSource).toContain('t(\'workbench.result_label\')');
  });
});
