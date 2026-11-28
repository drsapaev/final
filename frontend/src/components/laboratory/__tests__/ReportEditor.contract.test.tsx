import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
import { normalizeSource } from '../../../test/contracts/source-contract-helper';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

const source = normalizeSource(fs.readFileSync(
  path.join(ROOT, 'components/laboratory/ReportEditor.tsx'),
  'utf8'
));

const workbenchSource = normalizeSource(fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabReportWorkbench.tsx'),
  'utf8'
));

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
    ];
    for (const prop of expectedProps) {
      expect(source).toContain(prop);
    }
  });

  it('imports getEvaluationLabelKey, formatThreshold from labReportNormalize', () => {
    expect(source).toContain("from './utils/labReportNormalize'");
    expect(source).toContain('getEvaluationLabelKey');
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

  it('renders sections.map with collapsible headers', () => {
    expect(source).toContain('activeInstance.sections.map');
    expect(source).toContain('collapsedSections.has');
    expect(source).toContain('onToggleSection');
    expect(source).toContain('aria-expanded={!isCollapsed}');
  });

  it('renders saved server assessment and keeps clinical thresholds out of input event handlers', () => {
    expect(source).toContain("t(getEvaluationLabelKey(field))");
    expect(source).not.toContain('rangeMatch');
    expect(source).not.toContain('isCritical');
  });

  it('has STRAT#24 marker in JSDoc', () => {
    expect(source).toContain('STRAT#24');
  });

  it('LabReportWorkbench imports and uses ReportEditor', () => {
    expect(workbenchSource).toContain("import ReportEditor from './ReportEditor'");
    expect(workbenchSource).toContain('<ReportEditor');
    expect(workbenchSource).toContain('activeInstance={activeInstance}');
    // Contract: LabReportWorkbench must pass draftValues to ReportEditor.
    // After normalizeSource, 'as Record<...>' cast is removed but trailing space may remain.
    expect(workbenchSource).toContain('draftValues={draftValues');
    expect(workbenchSource).toContain('collapsedSections={collapsedSections}');
    expect(workbenchSource).toContain('onUpdateField={updateField}');
  });
});
