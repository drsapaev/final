import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ComponentProps } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
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
