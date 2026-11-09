/**
 * EMRTEMPL-FE-001 (audit 3886, round 23) — fail-first, generic panel.
 *
 * handleEditSave awaited updateTemplate, ignored its success flag and ALWAYS
 * closed the edit dialog + cleared the typed revision: on HTTP 400/403/500
 * or offline the doctor was returned to the list with the draft discarded
 * while the server template stayed unchanged — later reuse could apply the
 * older therapeutic text with no indication the correction had failed.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const panelState = vi.hoisted(() => ({
  update: vi.fn(),
  templates: [] as Record<string, unknown>[],
}));

vi.mock('../../../hooks/useDoctorSectionTemplates', () => ({
  useDoctorSectionTemplates: () => ({
    templates: panelState.templates,
    loading: false,
    error: null,
    hasTemplates: panelState.templates.length > 0,
    refetch: vi.fn(),
    pinTemplate: vi.fn(),
    unpinTemplate: vi.fn(),
    updateTemplate: (...args: unknown[]) => panelState.update(...args),
    deleteTemplate: vi.fn(),
    section: 'treatment',
    icd10Code: null,
  }),
  SECTION_LABELS: {
    complaints: 'Жалобы',
    anamnesis: 'Анамнез',
    examination: 'Осмотр',
    treatment: 'Лечение',
    recommendations: 'Рекомендации',
  },
}));

import { DoctorTemplatesPanel } from '../DoctorTemplatesPanel';
import { ThemeProvider } from '../../../contexts/ThemeContext';

beforeEach(() => {
  panelState.update.mockReset();
  panelState.templates = [{ id: 5, template_text: 'Старый текст шаблона', is_pinned: false }];
});

function renderPanel() {
  return render(
    <ThemeProvider>
      <DoctorTemplatesPanel
        section="treatment"
        icd10Code={null}
        isOpen
        onApply={vi.fn()}
        onClose={vi.fn()}
      />
    </ThemeProvider>,
  );
}

async function openEditorAndType() {
  fireEvent.click(screen.getByRole('button', { name: 'Редактировать шаблон врача' }));
  const textarea = screen.getByLabelText('Текст шаблона врача');
  fireEvent.change(textarea, { target: { value: 'Исправленная терапия' } });
  return textarea;
}

describe('EMRTEMPL-FE-001: a failed template update never discards the edit dialog', () => {
  it('failed Replace keeps the dialog open with the typed revision and surfaces the error', async () => {
    panelState.update.mockResolvedValueOnce({ success: false, error: 'HTTP 500: сервер недоступен' });
    renderPanel();

    const textarea = await openEditorAndType();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Заменить старый/i }));
    });

    // The dialog is still open with the typed revision intact…
    expect(screen.getByLabelText('Текст шаблона врача')).toHaveValue('Исправленная терапия');
    expect(textarea).toBeInTheDocument();
    // …and the failure is surfaced instead of silently closing.
    expect(screen.getByRole('alert')).toHaveTextContent('HTTP 500: сервер недоступен');
    expect(panelState.update).toHaveBeenCalledWith('5', 'Исправленная терапия', 'replace');
  });

  it('failed Save As New keeps the dialog open too', async () => {
    panelState.update.mockResolvedValueOnce({ success: false, error: 'HTTP 403' });
    renderPanel();

    await openEditorAndType();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Сохранить как новый/i }));
    });

    expect(screen.getByLabelText('Текст шаблона врача')).toHaveValue('Исправленная терапия');
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('a successful update closes the dialog and clears the draft (control)', async () => {
    panelState.update.mockResolvedValueOnce({ success: true, template: {} });
    renderPanel();

    await openEditorAndType();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Заменить старый/i }));
    });

    await waitFor(() => {
      expect(screen.queryByLabelText('Текст шаблона врача')).toBeNull();
    });
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
