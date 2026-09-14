import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useDirtyTransitionGuard } from '../useDirtyTransitionGuard';
import { ThemeProvider } from '@/contexts/ThemeContext';

const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 6; i += 1) {
      await Promise.resolve();
    }
  });
};

describe('useDirtyTransitionGuard (PR5)', () => {
  it('runs the transition immediately when nothing is dirty', () => {
    const { result } = renderHook(() => useDirtyTransitionGuard());
    const transition = vi.fn();

    act(() => {
      result.current.guardTransition(transition);
    });

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
    act(() => {
      result.current.guardTransition(transition);
    });
    expect(result.current.isDialogOpen).toBe(true);

    render(<ThemeProvider>{result.current.guardDialog}</ThemeProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));

    expect(save).not.toHaveBeenCalled();
    expect(transition).not.toHaveBeenCalled();
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
});
