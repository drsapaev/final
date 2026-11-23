import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * LABUX-FE-002 (audit 3886, round 13) — fail-first.
 *
 * Choice-поле клинического результата рендерилось нативным <select> БЕЗ
 * программного имени: видимый label — соседний <div><strong>, не <label>
 * для контрола. Скрин-ридер объявлял значение выбора, но не анализатор,
 * к которому оно относится — соседние choice-поля неразличимы. Числовые
 * и multiline-поля уже используют aria-label `Результат: <label>`;
 * choice обязан следовать тому же контракту. Падает на до-фиксном коде.
 */

const getInstanceMock = vi.hoisted(() => vi.fn());

vi.mock('../../api/labReporting', () => ({
  labReportingApi: {
    getInstance: getInstanceMock,
    listInstances: vi.fn(),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    downloadPdf: vi.fn(),
    markPrinted: vi.fn(),
    previewInstancePdf: vi.fn(),
  },
}));

vi.mock('../../../hooks/useLabReporting', () => ({
  useLabReporting: () => ({
    getInstance: getInstanceMock,
    listInstances: vi.fn(),
    createInstance: vi.fn(),
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    downloadPdf: vi.fn(),
    markPrinted: vi.fn(),
    previewInstancePdf: vi.fn(),
  }),
}));

vi.mock('./hooks/useLabToast', () => ({
  useLabToast: () => ({
    interactiveInfo: vi.fn(),
    interactiveWarning: vi.fn(),
    interactiveError: vi.fn(),
  }),
}));

import ReportEditorRaw from '../ReportEditor';

const ReportEditor = ReportEditorRaw as unknown as React.ComponentType<Record<string, unknown>>;

const ACTIVE_INSTANCE = {
  id: 91,
  template_id: 3,
  status: 'IN_PROGRESS',
  sections: [
    {
      key: 'general',
      title: 'Общий анализ',
      fields: [
        {
          field_key: 'blood_status',
          label: 'Кровь (визуальная оценка)',
          value_type: 'choice',
          choice_options: ['Норма', 'Отклонение'],
          required: true,
        },
        {
          field_key: 'urine_status',
          label: 'Моча (визуальная оценка)',
          value_type: 'choice',
          choice_options: ['Норма', 'Отклонение'],
          required: false,
        },
      ],
    },
  ],
};

const baseProps = {
  activeInstance: ACTIVE_INSTANCE,
  draftValues: {} as Record<string, string>,
  collapsedSections: new Set(),
  onToggleSection: vi.fn(),
  onUpdateField: vi.fn(),
  canEditActiveInstance: true,
  reportHistory: [],
  notify: vi.fn(),
};

beforeEach(async () => {
  vi.clearAllMocks();
  getInstanceMock.mockReset();
  getInstanceMock.mockResolvedValue(null);
  await i18n.changeLanguage('ru');
});

describe('LABUX-FE-002: choice dropdown exposes its clinical field label', () => {
  it('each choice select has an accessible name of the form `Результат: <анализатор>`', () => {
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} />
      </ThemeProvider>,
    );

    const blood = screen.getByRole('combobox', { name: 'Результат: Кровь (визуальная оценка)' });
    expect(blood).toBeEnabled();
    const urine = screen.getByRole('combobox', { name: 'Результат: Моча (визуальная оценка)' });
    expect(urine).toBeEnabled();
  });

  it('two adjacent choice fields are distinguishable by name (not just by position)', () => {
    render(
      <ThemeProvider>
        <ReportEditor {...baseProps} />
      </ThemeProvider>,
    );
    const combos = screen.getAllByRole('combobox');
    expect(combos).toHaveLength(2);
    const blood = screen.getByRole('combobox', { name: /Кровь/ });
    const urine = screen.getByRole('combobox', { name: /Моча/ });
    expect(blood).not.toBe(urine);
    within(blood as HTMLElement).getByRole('option', { name: 'Норма' });
  });
});
