/**
 * RETRO-3995-03 (post-merge review window 3969-3996, ledger PR 4000) — fail-first.
 *
 * The hook exposes `error` and carries typed shared failures {ok:false,error}
 * to every subscriber, but DoctorTemplatesPanel destructured only
 * templates/loading/hasTemplates: a failed GET rendered the SAME
 * "Нет сохранённых шаблонов" empty state as a successful zero-template
 * response — a false clinical statement (the doctor believes no personal
 * phrases exist when in fact the read failed), with no retry action.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const panelState = vi.hoisted(() => ({
  templates: [] as Record<string, unknown>[],
  loading: false,
  error: null as string | null,
  refetch: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('../../../hooks/useDoctorSectionTemplates', () => ({
  useDoctorSectionTemplates: () => ({
    templates: panelState.templates,
    loading: panelState.loading,
    error: panelState.error,
    hasTemplates: panelState.templates.length > 0,
    refetch: (...args: unknown[]) => panelState.refetch(...args),
    pinTemplate: vi.fn(),
    unpinTemplate: vi.fn(),
    updateTemplate: vi.fn(),
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
  panelState.templates = [];
  panelState.loading = false;
  panelState.error = null;
  panelState.refetch.mockReset();
});

function renderPanel(props: { section?: string; icd10Code?: string | null } = {}) {
  return render(
    <ThemeProvider>
      <DoctorTemplatesPanel
        section={props.section ?? 'treatment'}
        icd10Code={props.icd10Code ?? null}
        isOpen
        onApply={vi.fn()}
        onClose={vi.fn()}
      />
    </ThemeProvider>,
  );
}

describe('RETRO-3995-03: a failed GET is an error state, never a false "no saved templates"', () => {
  it('a failed GET surfaces the error with a retry action instead of the empty state', () => {
    panelState.error = 'HTTP 503: сервис недоступен';
    renderPanel();

    // The false clinical statement must NOT be shown…
    expect(screen.queryByText('Нет сохранённых шаблонов')).toBeNull();
    // …the failure is surfaced with its message…
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Не удалось загрузить шаблоны');
    expect(alert).toHaveTextContent('HTTP 503: сервис недоступен');
    // …and a retry action exists.
    const retry = screen.getByRole('button', { name: 'Повторить' });
    fireEvent.click(retry);
    expect(panelState.refetch).toHaveBeenCalledTimes(1);
  });

  it('a retry that succeeds restores the list', () => {
    panelState.error = 'HTTP 503: сервис недоступен';
    const utils = renderPanel();

    panelState.refetch.mockImplementation(() => {
      panelState.error = null;
      panelState.templates = [{ id: 7, template_text: 'Гидрокортизон 1%', is_pinned: false }];
      utils.rerender(
        <ThemeProvider>
          <DoctorTemplatesPanel section="treatment" icd10Code={null} isOpen onApply={vi.fn()} onClose={vi.fn()} />
        </ThemeProvider>,
      );
      return Promise.resolve({ ok: true, data: panelState.templates });
    });

    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));

    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('Гидрокортизон 1%')).toBeInTheDocument();
  });

  it('a true empty success keeps the benign empty state (no alert)', () => {
    renderPanel();
    expect(screen.getByText('Нет сохранённых шаблонов')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Повторить' })).toBeNull();
  });
});

describe('RETRO-3995-03: the previous error never survives a context switch (real hook)', () => {
  it('a section switch clears the failed context error synchronously', async () => {
    vi.resetModules();
    // The static vi.mock above must not shadow the real hook for the
    // dynamic import below — unmock it for the remainder of this test.
    vi.doUnmock('../../../hooks/useDoctorSectionTemplates');

    vi.doMock('../../../api/client', () => ({
      default: { get: apiMocks.get, post: apiMocks.post, put: apiMocks.put, delete: apiMocks.delete },
    }));
    vi.doMock('../../../stores/auth', () => ({
      getState: () => ({ profile: { id: 1 } }),
    }));
    const { useDoctorSectionTemplates } = await import('../../../hooks/useDoctorSectionTemplates');
    const { renderHook, act } = await import('@testing-library/react');

    // The treatment GET fails; the complaints GET succeeds.
    apiMocks.get.mockImplementation((url: string) => {
      if (String(url).includes('/section-templates/treatment')) {
        return Promise.reject(new Error('HTTP 503: сервис недоступен'));
      }
      return Promise.resolve({ data: { templates: [{ id: 1, template_text: 'Жалоба на головную боль' }] } });
    });

    const { result, rerender } = renderHook(
      (next: { section: string }) =>
        useDoctorSectionTemplates({ section: next.section, icd10Code: null }),
      { initialProps: { section: 'treatment' } },
    );

    await waitFor(() => expect(result.current.error).not.toBeNull());

    // Switch the section: the failed context's error must be gone
    // synchronously — the new context never paints the previous failure.
    act(() => {
      rerender({ section: 'complaints' });
    });
    expect(result.current.error).toBeNull();

    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.hasTemplates).toBe(true);
    // Exactly two GETs: the failed treatment read and the complaints read.
    expect(apiMocks.get).toHaveBeenCalledTimes(2);
  });
});
