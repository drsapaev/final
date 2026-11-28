import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ComponentProps } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import ReportSaveStatus from '../ReportSaveStatus';

const serverReport = {
  sections: [{ fields: [{ field_key: 'hgb', label: 'Гемоглобин', value_text: '145' }] }],
  available_actions: ['save_draft'],
};

function renderConflict() {
  const onCompare = vi.fn();
  function view(overrides: Partial<ComponentProps<typeof ReportSaveStatus>> = {}) {
    return (
      <ThemeProvider>
        <ReportSaveStatus
          language="ru"
          saving={false}
          isDirty
          lastSavedAt={null}
          failure="conflict"
          comparing={false}
          baseline={{ values: { hgb: '135' }, signer: {}, studyDate: '' }}
          current={{ values: { hgb: '140' }, signer: {}, studyDate: '' }}
          comparison={null}
          onRetry={vi.fn()}
          onCompare={onCompare}
          onResolve={vi.fn()}
          {...overrides}
        />
        <button type="button">Другой элемент</button>
      </ThemeProvider>
    );
  }

  const { rerender } = render(view());
  return { onCompare, rerender: (overrides: Partial<ComponentProps<typeof ReportSaveStatus>>) => rerender(view(overrides)) };
}

describe('draft conflict comparison keyboard focus', () => {
  it('keeps the trigger focused during loading and focuses the result when it replaces the trigger', async () => {
    const user = userEvent.setup();
    const { onCompare, rerender } = renderConflict();
    const compare = screen.getByRole('button', { name: 'Сравнить версии' });

    await user.tab();
    expect(compare).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(onCompare).toHaveBeenCalledTimes(1);

    rerender({ comparing: true });
    expect(compare).toHaveFocus();
    expect(compare).not.toBeDisabled();
    expect(compare).toHaveAttribute('aria-disabled', 'true');
    expect(compare).toHaveAttribute('aria-busy', 'true');
    await user.keyboard('{Enter}');
    expect(onCompare).toHaveBeenCalledTimes(1);

    rerender({ comparison: serverReport });
    expect(compare).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Изменения в бланке' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Перенести мои правки' })).toHaveFocus();
  });

  it('preserves focus when the user tabs away before the comparison arrives', async () => {
    const user = userEvent.setup();
    const { rerender } = renderConflict();

    await user.tab();
    await user.keyboard('{Enter}');
    rerender({ comparing: true });
    await user.tab();
    const nextControl = screen.getByRole('button', { name: 'Другой элемент' });
    expect(nextControl).toHaveFocus();

    rerender({ comparison: serverReport });
    expect(screen.getByRole('region', { name: 'Изменения в бланке' })).toBeVisible();
    expect(nextControl).toHaveFocus();
  });
});

it.each([
  ['ru', 'ФИО лаборанта', 'Подпись утверждающего'],
  ['uz-Cyrl', 'Лаборантнинг Ф.И.Ш.', 'Тасдиқловчи ходимнинг имзоси'],
  ['uz-Latn', 'Laborantning F.I.Sh.', 'Tasdiqlovchi xodimning imzosi'],
])('names signer field differences in %s', async (language, technicianName, approver) => {
  await i18n.changeLanguage(language);
  try {
    const { rerender } = renderConflict();
    rerender({
      language,
      current: { values: { hgb: '140' }, signer: { lab_technician_name: 'SYNTHETIC-LOCAL' }, studyDate: '' },
      comparison: { ...serverReport, signer_snapshot: { approver_label: 'SYNTHETIC-SERVER' } },
    });

    expect(screen.getByRole('rowheader', { name: technicianName })).toBeVisible();
    expect(screen.getByRole('rowheader', { name: approver })).toBeVisible();
    expect(screen.getByRole('cell', { name: 'SYNTHETIC-LOCAL' })).toBeVisible();
    expect(screen.getByRole('cell', { name: 'SYNTHETIC-SERVER' })).toBeVisible();
  } finally {
    cleanup();
    await i18n.changeLanguage('ru');
  }
});

it.each([
  ['ru', 'Сохранено в TIME', 'Последнее сохранение в TIME'],
  ['uz-Cyrl', 'TIME да сақланди', 'Охирги сақлаш TIME да'],
  ['uz-Latn', 'TIME da saqlandi', 'Oxirgi saqlash TIME da'],
])('shows the current and previous save time in %s', async (language, saved, previous) => {
  await i18n.changeLanguage(language);
  try {
    const lastSavedAt = new Date('2026-01-02T13:24:37Z');
    const time = lastSavedAt.toLocaleTimeString(language, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const { rerender } = renderConflict();
    rerender({ language, lastSavedAt, failure: null, isDirty: false });
    expect(screen.getByRole('status')).toHaveTextContent(saved.replace('TIME', time));

    rerender({ language, lastSavedAt, failure: null, isDirty: true });
    expect(screen.getByRole('status')).toHaveTextContent(previous.replace('TIME', time));
  } finally {
    cleanup();
    await i18n.changeLanguage('ru');
  }
});
