import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useDirtyTransitionGuard } from '../useDirtyTransitionGuard';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) {
      await Promise.resolve();
    }
  });
};

describe('useDirtyTransitionGuard (PR5)', () => {
  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('runs the transition immediately when nothing is dirty', () => {
    const { result } = renderHook(() => useDirtyTransitionGuard());
    const transition = vi.fn();
    let started = false;

    act(() => {
      started = result.current.guardTransition(transition);
    });

    expect(started).toBe(true);
    expect(transition).toHaveBeenCalledTimes(1);
    expect(result.current.isDialogOpen).toBe(false);
  });

  it('cancel keeps the user in place: no save, no transition', () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({ id: 'report', isDirty: () => true, save });
    });
    const transition = vi.fn();
    let started = true;
    act(() => {
      started = result.current.guardTransition(transition);
    });
    expect(started).toBe(false);
    expect(result.current.isDialogOpen).toBe(true);

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));

    expect(save).not.toHaveBeenCalled();
    expect(transition).not.toHaveBeenCalled();
    expect(result.current.isDialogOpen).toBe(false);
  });

  it('runs transition-specific cancel recovery without running the transition', () => {
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });
    const transition = vi.fn();
    const onCancel = vi.fn();
    act(() => {
      result.current.guardTransition(transition, { onCancel });
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(transition).not.toHaveBeenCalled();
  });

  it('can dismiss an obsolete pending transition without running cancel recovery', () => {
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
      });
      result.current.guardTransition(vi.fn(), { onCancel: vi.fn() });
    });

    act(() => {
      result.current.dismissPendingTransition();
    });

    expect(result.current.isDialogOpen).toBe(false);
  });

  it('discard continues the transition without saving', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({ id: 'report', isDirty: () => true, save });
    });
    const transition = vi.fn();
    act(() => {
      result.current.guardTransition(transition);
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Выйти без сохранения' }));
    await flush();

    expect(save).not.toHaveBeenCalled();
    expect(transition).toHaveBeenCalledTimes(1);
  });

  it('save continues the transition after a successful save', async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({ id: 'report', isDirty: () => true, save });
    });
    const transition = vi.fn();
    act(() => {
      result.current.guardTransition(transition);
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить и перейти' }));
    await flush();

    expect(save).toHaveBeenCalledTimes(1);
    expect(transition).toHaveBeenCalledTimes(1);
  });

  it('does not run an obsolete transition when a newer intent arrives during save', async () => {
    let resolveSave: (() => void) | undefined;
    const save = vi.fn(() => new Promise<void>((resolve) => {
      resolveSave = resolve;
    }));
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({ id: 'report', isDirty: () => true, save });
      result.current.guardTransition(vi.fn());
    });
    const obsoleteTransition = vi.fn();
    act(() => {
      result.current.guardTransition(obsoleteTransition);
    });
    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить и перейти' }));
    await act(async () => {
      await Promise.resolve();
    });

    const latestTransition = vi.fn();
    act(() => {
      result.current.guardTransition(latestTransition);
    });
    await act(async () => {
      resolveSave?.();
      await Promise.resolve();
    });

    expect(obsoleteTransition).not.toHaveBeenCalled();
    expect(latestTransition).not.toHaveBeenCalled();
    expect(result.current.isDialogOpen).toBe(true);
  });

  it('a failed save keeps the user in place and does not continue the transition', async () => {
    const save = vi.fn().mockRejectedValue(new Error('validation failed'));
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({ id: 'template', isDirty: () => true, save });
    });
    const transition = vi.fn();
    act(() => {
      result.current.guardTransition(transition);
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить и перейти' }));
    await flush();

    expect(save).toHaveBeenCalledTimes(1);
    expect(transition).not.toHaveBeenCalled();
  });

  it('a clean source does not trigger the dialog, a dirty one does', () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDirtyTransitionGuard());
    let dirty = false;
    act(() => {
      result.current.registerDirtySource({ id: 'report', isDirty: () => dirty, save });
    });
    const transition = vi.fn();

    act(() => {
      result.current.guardTransition(transition);
    });
    expect(transition).toHaveBeenCalledTimes(1);
    expect(result.current.isDialogOpen).toBe(false);

    dirty = true;
    act(() => {
      result.current.guardTransition(transition);
    });
    expect(result.current.isDialogOpen).toBe(true);
  });

  it('renders the dialog in the active locale', async () => {
    await act(async () => {
      await i18n.changeLanguage('uz-Latn');
    });
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
      });
      result.current.guardTransition(vi.fn());
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);

    expect(screen.getByRole('heading', { name: 'Saqlanmagan o\'zgarishlar' })).toBeInTheDocument();
    expect(screen.getByText('Blankada saqlanmagan o\'zgarishlar bor. O\'tishdan oldin ularni saqlaysizmi?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bekor qilish' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Saqlamasdan davom etish' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Saqlash va davom etish' })).toBeInTheDocument();
  });

  it('uses the localized cancel label in English', async () => {
    await act(async () => {
      await i18n.changeLanguage('en');
    });
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'template',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
      });
      result.current.guardTransition(vi.fn());
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);

    expect(screen.getByRole('heading', { name: 'Unsaved changes' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
  });

  // PR #3351: sourceIds — область перехода ограничена затрагиваемыми
  // источниками: dirty-отчёт не должен спрашивать подтверждение при смене
  // шаблона и наоборот.
  it('a dirty report does not guard a template-scoped transition', () => {
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
      });
      result.current.registerDirtySource({
        id: 'template',
        isDirty: () => false,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });

    const templateTransition = vi.fn();
    let started = false;
    act(() => {
      started = result.current.guardTransition(templateTransition, { sourceIds: ['template'] });
    });

    expect(started).toBe(true);
    expect(templateTransition).toHaveBeenCalledTimes(1);
    expect(result.current.isDialogOpen).toBe(false);
  });

  it('a dirty template guards a template-scoped transition but not a report-scoped one', () => {
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => false,
        save: vi.fn().mockResolvedValue(undefined),
      });
      result.current.registerDirtySource({
        id: 'template',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });

    const reportTransition = vi.fn();
    let reportStarted = false;
    act(() => {
      reportStarted = result.current.guardTransition(reportTransition, { sourceIds: ['report'] });
    });
    expect(reportStarted).toBe(true);
    expect(reportTransition).toHaveBeenCalledTimes(1);

    const templateTransition = vi.fn();
    let templateStarted = true;
    act(() => {
      templateStarted = result.current.guardTransition(templateTransition, { sourceIds: ['template'] });
    });
    expect(templateStarted).toBe(false);
    expect(templateTransition).not.toHaveBeenCalled();
    expect(result.current.isDialogOpen).toBe(true);
  });

  it('Discard resets the affected dirty sources before running the transition', async () => {
    const discardReport = vi.fn();
    const discardTemplate = vi.fn();
    const { result } = renderHook(() => useDirtyTransitionGuard());
    let reportDirty = true;
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => reportDirty,
        save: vi.fn().mockResolvedValue(undefined),
        discard: () => {
          reportDirty = false;
          discardReport();
        },
      });
      result.current.registerDirtySource({
        id: 'template',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
        discard: discardTemplate,
      });
    });

    const transition = vi.fn(() => {
      // К моменту запуска перехода сброшенный источник уже не dirty.
      expect(reportDirty).toBe(false);
    });
    act(() => {
      result.current.guardTransition(transition, { sourceIds: ['report'] });
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Выйти без сохранения' }));
    await flush();

    // Сброшен только затронутый источник; template-draft не тронут.
    expect(discardReport).toHaveBeenCalledTimes(1);
    expect(discardTemplate).not.toHaveBeenCalled();
    expect(transition).toHaveBeenCalledTimes(1);
  });

  it('Discard without a scope resets every dirty source', async () => {
    const discardA = vi.fn();
    const discardB = vi.fn();
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
        discard: discardA,
      });
      result.current.registerDirtySource({
        id: 'template',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
        discard: discardB,
      });
      result.current.guardTransition(vi.fn());
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Выйти без сохранения' }));
    await flush();

    expect(discardA).toHaveBeenCalledTimes(1);
    expect(discardB).toHaveBeenCalledTimes(1);
  });

  it('Escape on the document cancels the pending transition', async () => {
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({
        id: 'report',
        isDirty: () => true,
        save: vi.fn().mockResolvedValue(undefined),
      });
    });
    const transition = vi.fn();
    const onCancel = vi.fn();
    act(() => {
      result.current.guardTransition(transition, { onCancel });
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    expect(result.current.isDialogOpen).toBe(true);

    // PR #3351: Escape ловится capture-listener-ом на document при любой
    // позиции фокуса (здесь — body, как в E2E до автофокуса Modal).
    await act(async () => {
      fireEvent.keyDown(document.body, { key: 'Escape' });
    });

    expect(result.current.isDialogOpen).toBe(false);
    expect(transition).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('save-with-scope persists only the scoped dirty sources', async () => {
    const saveReport = vi.fn().mockResolvedValue(undefined);
    const saveTemplate = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDirtyTransitionGuard());
    act(() => {
      result.current.registerDirtySource({ id: 'report', isDirty: () => true, save: saveReport });
      result.current.registerDirtySource({ id: 'template', isDirty: () => true, save: saveTemplate });
      result.current.guardTransition(vi.fn(), { sourceIds: ['report'] });
    });

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить и перейти' }));
    await flush();

    expect(saveReport).toHaveBeenCalledTimes(1);
    expect(saveTemplate).not.toHaveBeenCalled();
  });
});
