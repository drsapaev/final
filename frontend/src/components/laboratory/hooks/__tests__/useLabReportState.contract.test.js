import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/hooks/useLabReportState.js'),
  'utf8'
);

describe('useLabReportState hook (STRAT#1)', () => {
  it('exports useLabReportState function', () => {
    expect(source).toContain('export function useLabReportState(');
  });

  it('imports hasLabReportAction from labReportActions utils', () => {
    expect(source).toContain('from \'../utils/labReportActions\'');
    expect(source).toContain('hasLabReportAction');
  });

  it('imports normalize helpers from labReportNormalize utils', () => {
    expect(source).toContain('from \'../utils/labReportNormalize\'');
    expect(source).toContain('extractFieldValue');
    expect(source).toContain('getServiceContextItems');
  });

  it('contains all expected state declarations', () => {
    const expectedStates = [
      'selectedTemplateId',
      'draftValues',
      'signerSnapshot',
      'collapsedSections',
      'saving',
      'busyAction',
      'printFeedback',
      'historySeverityFilter',
      'escapeHatchActive',
      'lastAutoSave',
      'autoSaving',
    ];
    for (const state of expectedStates) {
      expect(source).toContain(`[${state}, set${state.charAt(0).toUpperCase() + state.slice(1)}]`);
    }
  });

  it('contains all expected derived memos', () => {
    const useMemoMemos = [
      'isDirty',
      'publishedTemplates',
      'serviceContextItems',
      'missingRequiredFields',
    ];
    for (const memo of useMemoMemos) {
      expect(source).toContain(`const ${memo} = useMemo(`);
    }
    // canFinalizeWithValidation — это обычный const (не useMemo), проверяем отдельно
    expect(source).toContain('canFinalizeWithValidation');
  });

  it('contains all action availability flags', () => {
    expect(source).toContain('hasLabReportAction(activeInstance, \'edit\')');
    expect(source).toContain('hasLabReportAction(activeInstance, \'save_draft\')');
    expect(source).toContain('hasLabReportAction(activeInstance, \'finalize\')');
    expect(source).toContain('hasLabReportAction(activeInstance, \'revise\')');
    expect(source).toContain('hasLabReportAction(activeInstance, \'print\')');
  });

  it('contains init-instance effect that loads values from activeInstance', () => {
    expect(source).toContain('useEffect(() => {');
    expect(source).toContain('if (!activeInstance) {');
    expect(source).toContain('setDraftValues({})');
    expect(source).toContain('values[field.field_key] = extractFieldValue(field)');
  });

  it('contains default template selection effect', () => {
    expect(source).toContain('defaultTemplateId');
    expect(source).toContain('setSelectedTemplateId((current) => {');
  });

  it('returns all state, setters, refs, and derived values', () => {
    expect(source).toContain('return {');
    expect(source).toContain('selectedTemplateId,');
    expect(source).toContain('setSelectedTemplateId,');
    expect(source).toContain('isDirty,');
    expect(source).toContain('canFinalizeWithValidation,');
    expect(source).toContain('handleSaveDraftRef,');
    expect(source).toContain('autoSaveTimerRef,');
  });

  it('has STRAT#1 marker in JSDoc', () => {
    expect(source).toContain('STRAT#1');
  });
});
