// src/hooks/__tests__/useDebouncedCallback.test.ts
// Phase 2 batch 1 — unit tests for useDebouncedCallback / useDebouncedValue.
// Covers: happy path, cancel/flush, debounced value, policy-key delay.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebouncedCallback, useDebouncedValue } from '../useDebouncedCallback';

describe('useDebouncedCallback', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('invokes callback after delay (number)', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 500));

    result.current('arg1', 'arg2');
    expect(cb).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(cb).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith('arg1', 'arg2');
  });

  it('invokes callback after delay (policy key)', () => {
    const cb = vi.fn();
    // 'search' = 500ms per debouncePolicy.ts
    const { result } = renderHook(() => useDebouncedCallback(cb, 'search'));

    result.current();
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('cancel() prevents pending invocation', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 500));

    result.current();
    result.current.cancel();

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(cb).not.toHaveBeenCalled();
  });

  it('flush() invokes callback immediately and clears pending', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 500));

    result.current('first');
    result.current.flush('second');

    // flush должен вызвать сразу
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith('second');

    // Pending таймер должен быть отменён
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('subsequent calls reset the timer (debounce semantics)', () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 500));

    result.current();
    act(() => {
      vi.advanceTimersByTime(400);
    });
    result.current();
    act(() => {
      vi.advanceTimersByTime(400);
    });
    // 800ms прошло, но вызова нет — последний call был 400ms назад
    expect(cb).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(cb).toHaveBeenCalledTimes(1);
  });
});

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('initial', 500));
    expect(result.current).toBe('initial');
  });

  it('updates value after delay', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 500), {
      initialProps: { value: 'first' },
    });

    rerender({ value: 'second' });
    expect(result.current).toBe('first');

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current).toBe('second');
  });

  it('works with policy key delay', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 'ui'), {
      initialProps: { value: 1 },
    });

    rerender({ value: 2 });
    act(() => {
      vi.advanceTimersByTime(150); // 'ui' = 150ms
    });
    expect(result.current).toBe(2);
  });
});
