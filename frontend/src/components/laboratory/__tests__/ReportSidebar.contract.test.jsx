import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/ReportSidebar.tsx'),
  'utf8'
);

const workbenchSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabReportWorkbench.tsx'),
  'utf8'
);

describe('ReportSidebar STRAT#25 — extracted sub-component', () => {
  it('exports default ReportSidebar component', () => {
    expect(source).toContain('export default function ReportSidebar(');
  });

  it('imports LabReportHistoryPanel and LabReportAIAnalysis', () => {
    expect(source).toContain("from './LabReportHistoryPanel'");
    expect(source).toContain("from './LabReportAIAnalysis'");
  });

  it('accepts all expected props', () => {
    const expectedProps = [
      'activeInstance',
      'notify',
      'showRecentReportsBrowser',
      'recentReports',
      'reportHistory',
      'historySeverityFilter',
      'onSeverityFilterChange',
      'onOpenInstance',
    ];
    for (const prop of expectedProps) {
      expect(source).toContain(prop);
    }
  });

  it('renders LabReportAIAnalysis when activeInstance is present', () => {
    expect(source).toContain('showAI');
    expect(source).toContain('Boolean(activeInstance)');
    expect(source).toContain('<LabReportAIAnalysis');
  });

  it('renders LabReportHistoryPanel when history data is available', () => {
    expect(source).toContain('showHistory');
    expect(source).toContain('showRecentReportsBrowser || reportHistory.length > 0');
    expect(source).toContain('<LabReportHistoryPanel');
  });

  it('returns null when neither AI nor history should show', () => {
    expect(source).toContain('if (!showHistory && !showAI)');
    expect(source).toContain('return null');
  });

  it('has STRAT#25 marker in JSDoc', () => {
    expect(source).toContain('STRAT#25');
  });

  it('LabReportWorkbench imports and uses ReportSidebar', () => {
    expect(workbenchSource).toContain("import ReportSidebar from './ReportSidebar'");
    expect(workbenchSource).toContain('<ReportSidebar');
    expect(workbenchSource).toContain('activeInstance={activeInstance}');
    expect(workbenchSource).toContain('showRecentReportsBrowser={showRecentReportsBrowser}');
    expect(workbenchSource).toContain('onOpenInstance={onOpenInstance}');
  });

  it('LabReportWorkbench no longer directly imports LabReportAIAnalysis or LabReportHistoryPanel', () => {
    // STRAT#25: these are now imported by ReportSidebar, not by LabReportWorkbench
    expect(workbenchSource).not.toContain("import LabReportAIAnalysis from './LabReportAIAnalysis'");
    expect(workbenchSource).not.toContain("import LabReportHistoryPanel from './LabReportHistoryPanel'");
  });
});
