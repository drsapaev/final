import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/ReportEditor.jsx'),
  'utf8'
);

const workbenchSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabReportWorkbench.jsx'),
  'utf8'
);

describe('ReportEditor STRAT#24 — extracted sub-component', () => {
  it('exports default ReportEditor component', () => {
    expect(source).toContain('export default function ReportEditor(');
  });

  it('accepts all expected props', () => {
    const expectedProps = [
      'activeInstance',
      'draftValues',
      'collapsedSections',
      'onToggleSection',
      'onUpdateField',
      'canEditActiveInstance',
      'reportHistory',
      'notify',
    ];
    for (const prop of expectedProps) {
      expect(source).toContain(prop);
    }
  });

  it('imports formatFlagLabel, formatThreshold from labReportNormalize', () => {
    expect(source).toContain("from './utils/labReportNormalize'");
    expect(source).toContain('formatFlagLabel');
    expect(source).toContain('formatThreshold');
  });

  it('imports flagVariant from labReportActions', () => {
    expect(source).toContain("from './utils/labReportActions'");
    expect(source).toContain('flagVariant');
  });

  it('imports t from unified i18n for i18n', () => {
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');
  });

  it('imports useLabToast for interactive numeric validation', () => {
    expect(source).toContain("from './hooks/useLabToast'");
    expect(source).toContain('useLabToast');
  });

  it('renders sections.map with collapsible headers', () => {
    expect(source).toContain('activeInstance.sections.map');
    expect(source).toContain('collapsedSections.has');
    expect(source).toContain('onToggleSection');
    expect(source).toContain('aria-expanded={!isCollapsed}');
  });

  it('handles numeric onBlur validation with labToast', () => {
    expect(source).toContain('labToast.interactiveError');
    expect(source).toContain('labToast.interactiveWarning');
    expect(source).toContain('labToast.interactiveInfo');
    expect(source).toContain("field.value_type === 'numeric'");
  });

  it('has STRAT#24 marker in JSDoc', () => {
    expect(source).toContain('STRAT#24');
  });

  it('LabReportWorkbench imports and uses ReportEditor', () => {
    expect(workbenchSource).toContain("import ReportEditor from './ReportEditor'");
    expect(workbenchSource).toContain('<ReportEditor');
    expect(workbenchSource).toContain('activeInstance={activeInstance}');
    expect(workbenchSource).toContain('draftValues={draftValues}');
    expect(workbenchSource).toContain('collapsedSections={collapsedSections}');
    expect(workbenchSource).toContain('onUpdateField={updateField}');
  });
});
