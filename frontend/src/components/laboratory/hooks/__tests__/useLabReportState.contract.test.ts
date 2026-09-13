import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../../..');

const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/hooks/useLabReportState.ts'),
  'utf8'
);

import { useLabReportState } from '../useLabReportState';

describe('useLabReportState hook (STRAT#1)', () => {
  it('exports useLabReportState function', () => {
    expect(source).toContain('export function useLabReportState(');
  });

  it('imports hasLabReportAction from labReportActions utils', () => {
    expect(source).toContain("from '../utils/labReportActions'");
    expect(source).toContain('hasLabReportAction');
  });

  it('imports normalize helpers from labReportNormalize utils', () => {
    expect(source).toContain("from '../utils/labReportNormalize'");
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
    expect(source).toContain("hasLabReportAction(activeInstance, 'edit')");
    expect(source).toContain("hasLabReportAction(activeInstance, 'save_draft')");
    expect(source).toContain("hasLabReportAction(activeInstance, 'finalize')");
    expect(source).toContain("hasLabReportAction(activeInstance, 'revise')");
    expect(source).toContain("hasLabReportAction(activeInstance, 'print')");
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

describe('useLabReportState draft hydration (PR3)', () => {
  const reopenedDraftInstance = {
    id: 77,
    status: 'DRAFT',
    template_id: 3,
    updated_at: '2026-09-13T08:00:00.000000+00:00',
    signer_snapshot: {},
    available_actions: ['edit', 'save_draft', 'finalize'],
    sections: [
      {
        key: 'cbc',
        title: 'CBC',
        fields: [
          {
            field_key: 'wbc',
            label: 'Лейкоциты',
            value_type: 'text',
            value_text: '5.2',
            comment: 'утренний забор',
          },
          {
            field_key: 'hgb',
            label: 'Гемоглобин',
            value_type: 'numeric',
            value_text: '140',
            comment: null,
          },
        ],
      },
    ],
  };

  it('hydrates field_key__comment keys from materialized field comments', () => {
    const { result } = renderHook(() =>
      useLabReportState({ activeInstance: reopenedDraftInstance })
    );

    expect(result.current.draftValues['wbc__comment']).toBe('утренний забор');
    // Поле без комментария гидратируется пустой строкой, чтобы повторное
    // сохранение отправляло прежнее состояние, а не null по умолчанию.
    expect(result.current.draftValues['hgb__comment']).toBe('');
  });

  it('keeps the reopened draft clean (not dirty) right after hydration', () => {
    const { result } = renderHook(() =>
      useLabReportState({ activeInstance: reopenedDraftInstance })
    );

    expect(result.current.isDirty).toBe(false);
  });
});
