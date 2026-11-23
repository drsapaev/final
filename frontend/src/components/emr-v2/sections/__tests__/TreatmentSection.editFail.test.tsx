/**
 * EMRTEMPL-FE-001 (audit 3886, round 23) — fail-first, treatment section.
 *
 * Both edit buttons («Заменить старый» / «Сохранить как новый») awaited
 * updateTemplate, ignored the returned boolean and always closed the modal:
 * on a failed PUT the typed revision was silently discarded while the server
 * template stayed unchanged.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const tsState = vi.hoisted(() => ({
  update: vi.fn(),
  templates: [] as Record<string, unknown>[],
}));

vi.mock('@/hooks/useDoctorTreatmentTemplates', () => ({
  useDoctorTreatmentTemplates: () => ({
    templates: tsState.templates,
    loading: false,
    error: null,
    hasTemplates: tsState.templates.length > 0,
    refetch: vi.fn(),
    pinTemplate: vi.fn(),
    unpinTemplate: vi.fn(),
    updateTemplate: (...args: unknown[]) => tsState.update(...args),
  }),
}));

vi.mock('@/hooks/useDoctorPhrases', () => ({
  useDoctorPhrases: () => ({ suggestions: [], loading: false }),
}));

import TreatmentSection from '../TreatmentSection';
import { ThemeProvider } from '../../../../contexts/ThemeContext';

beforeEach(() => {
  tsState.update.mockReset();
  tsState.templates = [{
    id: 7,
    treatment_text: 'Старая схема лечения',
    icd10_code: 'I10',
    is_pinned: false,
  }];
});

function renderSection() {
  return render(
    <ThemeProvider>
      <TreatmentSection
        value=""
        onChange={vi.fn()}
        icd10Code="I10"
        doctorId={42}
      />
    </ThemeProvider>,
  );
}

async function openEditorAndType() {
  // Open the «Мой опыт» panel (personal treatment patterns by ICD-10).
  fireEvent.click(screen.getByRole('button', { name: /Мой опыт/i }));
  // Start editing the template.
  fireEvent.click(screen.getByRole('button', { name: 'Редактировать шаблон лечения' }));
  const textarea = screen.getByLabelText('Текст шаблона лечения');
  fireEvent.change(textarea, { target: { value: 'Скорректированная схема' } });
  return textarea;
}

describe('EMRTEMPL-FE-001: failed treatment-template updates keep the revision', () => {
  it('failed Replace keeps the modal open with the typed text and shows the error', async () => {
    tsState.update.mockResolvedValueOnce(false);
    renderSection();

    await openEditorAndType();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Заменить старый/i }));
    });

    // The modal stays open, the typed revision survives…
    expect(screen.getByLabelText('Текст шаблона лечения')).toHaveValue('Скорректированная схема');
    // …and the failure is surfaced.
    expect(screen.getByRole('alert')).toHaveTextContent(/Не удалось сохранить/i);
    expect(tsState.update).toHaveBeenCalledWith('7', 'Скорректированная схема', 'replace');
  });

  it('failed Save As New keeps the modal open too', async () => {
    tsState.update.mockResolvedValueOnce(false);
    renderSection();

    await openEditorAndType();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить как новый/i }));
    });

    expect(screen.getByLabelText('Текст шаблона лечения')).toHaveValue('Скорректированная схема');
    expect(screen.getByRole('alert')).toHaveTextContent(/Не удалось сохранить/i);
  });

  it('a successful update closes the modal (control)', async () => {
    tsState.update.mockResolvedValueOnce(true);
    renderSection();

    await openEditorAndType();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Заменить старый/i }));
    });

    await waitFor(() => {
      expect(screen.queryByLabelText('Текст шаблона лечения')).toBeNull();
    });
  });
});
